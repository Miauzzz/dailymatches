import os
import requests
from flask import Blueprint, request, Response
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import summoners_collection
from dotenv import load_dotenv
from flask_caching import Cache

load_dotenv()

RIOT_API_KEY = os.getenv('RIOT_API_KEY')
summoner_bp = Blueprint('summoner', __name__)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

# Configuración de constantes
SOLOQ_QUEUE_ID = 420 # ID de cola para SoloQ
FLEXQ_QUEUE_ID = 440 # ID de cola para FlexQ
VALID_QUEUES = {
    'soloq': SOLOQ_QUEUE_ID,
    'flexq': FLEXQ_QUEUE_ID
}


def get_summoner_info(summoner_name, tagline):
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None



def get_summoner_id(puuid):
    url = f"https://la2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None



def get_league_info(puuid):
    url = f"https://la2.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None



def get_matches(puuid):
    chile_tz = ZoneInfo("America/Santiago")
    now = datetime.now(tz=chile_tz)
    
    # Si son las 3:59 AM, cuenta desde las 4 AM del día ANTERIOR
    if now.hour < 4:
        start_time = (now - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    else:
        start_time = now.replace(hour=4, minute=0, second=0, microsecond=0)
    
    end_time = start_time + timedelta(days=1)  # 4 AM del día siguiente
    
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={int(start_time.timestamp())}&endTime={int(end_time.timestamp())}&api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else []



def get_match_details(match_id):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None



def process_matches(puuid, queue_type):
    matches = get_matches(puuid)
    wins, losses = 0, 0
    target_queue = VALID_QUEUES[queue_type]

    for match_id in matches:
        match_details = get_match_details(match_id)
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



@summoner_bp.route('/<queue_type>/<summoner>/<tagline>', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def get_queue_stats(queue_type, summoner, tagline):
    chile_tz = ZoneInfo("America/Santiago")
    now = datetime.now(tz=chile_tz)

    # Resetear contadores si ya pasaron las 4 AM y no se ha actualizado hoy
    summoner_data = summoners_collection.find_one({"summoner": summoner.lower(), "tagline": tagline.lower()})
    if summoner_data:
        last_update = summoner_data.get("last_update").replace(tzinfo=chile_tz)
        if now.hour >= 4 and last_update.hour < 4 and last_update.date() < now.date():
            summoners_collection.update_one(
                {"puuid": summoner_data["puuid"]},
                {"$set": {
                    f"{queue_type}_wins": 0,
                    f"{queue_type}_losses": 0,
                    "last_update": now  # Actualizar marca de tiempo
                }}
            )

    if queue_type not in VALID_QUEUES:
        return Response("Tipo de cola inválido", status=400, mimetype='text/plain')
    summoner = summoner.lower()
    tagline = tagline.lower()
    summoner_data = summoners_collection.find_one({"summoner": summoner, "tagline": tagline})
    
    if not summoner_data:
        return Response("No existe el invocador en la base de datos", status=404, mimetype='text/plain')

    puuid = summoner_data['puuid']

    wins, losses = process_matches(puuid, queue_type)
    
    # Obtener información de liga
    league_info = get_league_info(puuid)
    if not league_info:
        print(f"[DEBUG] league_info está vacío o None para puuid={puuid}")
    else:
        print(f"[DEBUG] league_info queueTypes: {[entry.get('queueType') for entry in league_info]}")
    tier, rank, lp = get_queue_league_info(league_info, queue_type) if league_info else (None, None, None)
    

    
    # Actualizar base de datos
    update_data = {
        f"{queue_type}_wins": wins,
        f"{queue_type}_losses": losses,
        f"{queue_type}_tier": tier,
        f"{queue_type}_rank": rank,
        f"{queue_type}_lp": lp,
        "last_update": datetime.now(ZoneInfo("America/Santiago"))
    }
    
    summoners_collection.update_one(
        {"puuid": puuid},
        {"$set": update_data}
    )

    league_status = (
        f"| {tier} {rank} ({lp} LP)"
        if tier and rank and lp is not None
        else "| Y no tiene liga asignada"
    )
    formatted_last_update = update_data['last_update'].strftime("%H:%M")
    response_message = f"Victorias: {wins} / Derrotas: {losses} {league_status} (Act. {formatted_last_update})"
    
    return Response(response_message, mimetype='text/plain')

@summoner_bp.route('/', methods=['POST'])
def add_summoner():
    if not request.is_json:
        return Response("El cuerpo de la solicitud debe ser JSON", status=400, mimetype='text/plain')

    data = request.get_json()
    summoner_name = data.get('summoner_name', '').lower()
    tagline = data.get('tagline', '').lower()

    if not summoner_name or not tagline:
        return Response("Faltan datos", status=400, mimetype='text/plain')

    # Verificar si ya existe el summoner
    summoner_info = get_summoner_info(summoner_name, tagline)
    if not summoner_info:
        return Response("No existe el invocador en Riot", status=404, mimetype='text/plain')

    puuid = summoner_info['puuid']
    if summoners_collection.find_one({"puuid": puuid}):
        return Response("El invocador ya existe en la base de datos", status=400, mimetype='text/plain')

    summoner_id_info = get_summoner_id(puuid)
    if not summoner_id_info:
        return Response("Error al obtener datos del invocador", status=500, mimetype='text/plain')

    league_info = get_league_info(puuid)
    if not league_info:
        print(f"[DEBUG] league_info está vacío o None para puuid={puuid}")
    else:
        print(f"[DEBUG] league_info queueTypes: {[entry.get('queueType') for entry in league_info]}")
    soloq_tier, soloq_rank, soloq_lp = get_queue_league_info(league_info, 'soloq') if league_info else (None, None, None)
    flexq_tier, flexq_rank, flexq_lp = get_queue_league_info(league_info, 'flexq') if league_info else (None, None, None)

    # Insertar nuevo summoner
    new_summoner = {
        "puuid": puuid,
        "summoner": summoner_name,
        "tagline": tagline,
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
        "last_update": datetime.now()
    }
    
    summoners_collection.insert_one(new_summoner)
    return Response("Invocador agregado exitosamente", status=201, mimetype='text/plain')
    
    summoners_collection.insert_one(new_summoner)
    return Response("Invocador agregado exitosamente", status=201, mimetype='text/plain')
