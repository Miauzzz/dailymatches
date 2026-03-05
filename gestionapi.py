import os
import requests
import pytz  # <--- USAMOS PYTZ EN LUGAR DE ZONEINFO
from datetime import datetime, timedelta
from db import summoners_collection
from dotenv import load_dotenv

load_dotenv()

RIOT_API_KEY = os.getenv('RIOT_API_KEY')

# Configuración de constantes
SOLOQ_QUEUE_ID = 420 
FLEXQ_QUEUE_ID = 440 
VALID_QUEUES = {
    'soloq': SOLOQ_QUEUE_ID,
    'flexq': FLEXQ_QUEUE_ID
}

# Mapeo de server (plataforma) a host de API
PLATFORM_HOSTS = {
    'na1':  'na1.api.riotgames.com',
    'la1':  'la1.api.riotgames.com',
    'la2':  'la2.api.riotgames.com',
    'br1':  'br1.api.riotgames.com',
    'euw1': 'euw1.api.riotgames.com',
    'eun1': 'eun1.api.riotgames.com',
    'tr1':  'tr1.api.riotgames.com',
    'ru':   'ru.api.riotgames.com',
    'kr':   'kr.api.riotgames.com',
    'jp1':  'jp1.api.riotgames.com',
    'oc1':  'oc1.api.riotgames.com',
}

# Mapeo de server a endpoint regional (match/v5, account/v1)
PLATFORM_TO_REGIONAL = {
    'na1':  'americas',
    'la1':  'americas',
    'la2':  'americas',
    'br1':  'americas',
    'euw1': 'europe',
    'eun1': 'europe',
    'tr1':  'europe',
    'ru':   'europe',
    'kr':   'asia',
    'jp1':  'asia',
    'oc1':  'sea',
}

# --- FUNCIONES AUXILIARES ---

def get_summoner_info(summoner_name, tagline, region):
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def get_summoner_id(puuid, server):
    platform = PLATFORM_HOSTS[server]
    url = f"https://{platform}/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def get_league_info(puuid, server):
    platform = PLATFORM_HOSTS[server]
    url = f"https://{platform}/lol/league/v4/entries/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def get_matches(puuid, region):
    # Usamos pytz para la zona horaria
    chile_tz = pytz.timezone("America/Santiago")
    now = datetime.now(chile_tz)
    
    # Lógica de las 4 AM
    if now.hour < 4:
        start_time = (now - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        start_time = now.replace(hour=4, minute=0, second=0, microsecond=0)
    
    end_time = start_time + timedelta(days=1)
    
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={int(start_time.timestamp())}&endTime={int(end_time.timestamp())}&api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else []

def get_match_details(match_id, region):
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def process_matches(puuid, queue_type, region):
    matches = get_matches(puuid, region)
    wins, losses = 0, 0
    target_queue = VALID_QUEUES[queue_type]

    for match_id in matches:
        match_details = get_match_details(match_id, region)
        if match_details and match_details['info']['queueId'] == target_queue:
            if match_details['info']['gameDuration'] >= 300:
                for participant in match_details['info']['participants']:
                    if participant['puuid'] == puuid:
                        if participant['win']:
                            wins += 1
                        else:
                            losses += 1
                        break
    return wins, losses

def get_queue_league_info(league_info, queue_type):
    target_queue = 'RANKED_SOLO_5x5' if queue_type == 'soloq' else 'RANKED_FLEX_SR'
    for entry in league_info:
        if entry['queueType'] == target_queue:
            return entry['tier'], entry['rank'], entry['leaguePoints']
    return None, None, None

# --- LÓGICA PRINCIPAL (LLAMADA POR AZURE) ---

def logic_get_queue_stats(queue_type, server, summoner, tagline):
    chile_tz = pytz.timezone("America/Santiago")
    now = datetime.now(chile_tz)

    if queue_type not in VALID_QUEUES:
        return {"error": "Tipo de cola inválido", "status": 400}
    if server not in PLATFORM_HOSTS:
        return {"error": f"Servidor inválido. Válidos: {list(PLATFORM_HOSTS.keys())}", "status": 400}

    region = PLATFORM_TO_REGIONAL[server]
    summoner = summoner.lower()
    tagline = tagline.lower()
    
    summoner_data = summoners_collection.find_one({"summoner": summoner, "tagline": tagline, "server": server})
    
    if not summoner_data:
        return {"error": "No existe el invocador en la base de datos", "status": 404}

    # Reset diario (Lógica 4 AM)
    # El "día-juego" empieza a las 4 AM: si son las 3 AM, pertenece al día anterior
    last_update = summoner_data.get("last_update")
    if last_update.tzinfo is None:
        last_update = pytz.utc.localize(last_update).astimezone(chile_tz)
    else:
        last_update = last_update.astimezone(chile_tz)

    game_day_now = (now - timedelta(hours=4)).date()
    game_day_last = (last_update - timedelta(hours=4)).date()

    if game_day_now > game_day_last:
        summoners_collection.update_one(
            {"puuid": summoner_data["puuid"]},
            {"$set": {
                f"{queue_type}_wins": 0,
                f"{queue_type}_losses": 0,
                "last_update": now
            }}
        )

    puuid = summoner_data['puuid']
    wins, losses = process_matches(puuid, queue_type, region)
    
    league_info = get_league_info(puuid, server)
    tier, rank, lp = get_queue_league_info(league_info, queue_type) if league_info else (None, None, None)
    
    # Actualizar BD
    update_data = {
        f"{queue_type}_wins": wins,
        f"{queue_type}_losses": losses,
        f"{queue_type}_tier": tier,
        f"{queue_type}_rank": rank,
        f"{queue_type}_lp": lp,
        "last_update": now 
    }
    
    summoners_collection.update_one({"puuid": puuid}, {"$set": update_data})

    league_status = (
        f"| {tier} {rank} ({lp} LP)"
        if tier and rank and lp is not None
        else "| Y no tiene liga asignada"
    )
    formatted_last_update = update_data['last_update'].strftime("%H:%M")
    
    return {"message": f"Victorias: {wins} / Derrotas: {losses} {league_status} (Act. {formatted_last_update})", "status": 200}

def logic_add_summoner(data):
    chile_tz = pytz.timezone("America/Santiago")
    summoner_name = data.get('summoner_name', '').lower()
    tagline = data.get('tagline', '').lower()
    server = data.get('server', '').lower()

    if not summoner_name or not tagline or not server:
        return {"message": "Faltan datos (summoner_name, tagline, server)", "status": 400}
    if server not in PLATFORM_HOSTS:
        return {"message": f"Servidor inválido. Válidos: {list(PLATFORM_HOSTS.keys())}", "status": 400}

    region = PLATFORM_TO_REGIONAL[server]

    summoner_info = get_summoner_info(summoner_name, tagline, region)
    if not summoner_info:
        return {"message": "No existe el invocador en Riot", "status": 404}

    puuid = summoner_info['puuid']
    if summoners_collection.find_one({"puuid": puuid, "server": server}):
        return {"message": "El invocador ya existe en la base de datos", "status": 400}

    summoner_id_info = get_summoner_id(puuid, server)
    if not summoner_id_info:
        return {"message": "Error al obtener datos del invocador", "status": 500}

    league_info = get_league_info(puuid, server)
    soloq_tier, soloq_rank, soloq_lp = get_queue_league_info(league_info, 'soloq') if league_info else (None, None, None)
    flexq_tier, flexq_rank, flexq_lp = get_queue_league_info(league_info, 'flexq') if league_info else (None, None, None)

    new_summoner = {
        "puuid": puuid,
        "summoner": summoner_name,
        "tagline": tagline,
        "server": server,
        "id_summoner": summoner_id_info['id'],
        "soloq_wins": 0,
        "soloq_losses": 0,
        "soloq_tier": soloq_tier,
        "soloq_rank": soloq_rank,
        "soloq_lp": soloq_lp,
        "flexq_wins": 0,
        "flexq_losses": 0,
        "flexq_tier": flexq_tier,
        "flexq_rank": flexq_rank,
        "flexq_lp": flexq_lp,
        "last_update": datetime.now(chile_tz) # Usamos zona horaria explícita
    }
    
    summoners_collection.insert_one(new_summoner)
    return {"message": "Invocador agregado exitosamente", "status": 201}
