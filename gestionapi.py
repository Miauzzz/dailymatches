import os
import requests
from flask import Blueprint, request, jsonify, Response
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import summoners_collection
from dotenv import load_dotenv
from collections import OrderedDict
from flask_caching import Cache

load_dotenv()

RIOT_API_KEY = os.getenv('RIOT_API_KEY')
summoner_bp = Blueprint('summoner', __name__)

# Configuración de caché
cache = Cache()

def get_summoner_info(summoner_name, tagline):
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_summoner_id(puuid):
    url = f"https://la2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_league_info(summoner_id):
    url = f"https://la2.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def get_matches(puuid):
    chile_tz = ZoneInfo("America/Santiago")
    now = datetime.now(tz=chile_tz)
    start_time = datetime(now.year, now.month, now.day, tzinfo=chile_tz)
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(now.timestamp())
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={start_timestamp}&endTime={end_timestamp}&api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else []

def get_match_details(match_id):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

@summoner_bp.route('/<summoner_name>/<tagline>', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def get_summoner_stats(summoner_name, tagline):
    chile_tz = ZoneInfo("America/Santiago")
    summoner_name = summoner_name.lower()
    tagline = tagline.lower()
    summoner = summoners_collection.find_one({"summoner_name": summoner_name, "tagline": tagline})
    if not summoner:
        return Response("No existe el invocador en la base de datos", status=404, mimetype='text/plain')

    puuid = summoner['puuid']
    summoner_id = summoner['id']
    matches = get_matches(puuid)
    wins, losses = 0, 0

    # Tipos de partidas a contar
    # [400,   450,  420,      440] 
    # Normal, ARAM, Solo/Duo, Flex
    game_types_to_count = [420]
    
    for match_id in matches:
        match_details = get_match_details(match_id)
        if match_details:
            game_duration = match_details['info']['gameDuration']
            if game_duration < 300:  # Filtrar partidas "remake" (menos de 5 minutos)
                continue
            game_type = match_details['info']['queueId']
            if game_type not in game_types_to_count:
                continue
            for participant in match_details['info']['participants']:
                if participant['puuid'] == puuid:
                    if participant['win']:
                        wins += 1
                    else:
                        losses += 1
                    break

    league_info = get_league_info(summoner_id)
    if league_info:
        league = league_info[0]['tier']
        rank = league_info[0]['rank']
        lp = league_info[0]['leaguePoints']
        league_status = f"y se encuentra en {league} {rank} ({lp} LP)"
    else:
        league_status = "y no tiene liga asignada"
        league = None
        rank = None
        lp = None

    last_update = datetime.now(tz=chile_tz)
    summoners_collection.update_one(
        {"summoner_name": summoner_name, "tagline": tagline},
        {"$set": {"wins": wins, "losses": losses, "tier": league, "rank": rank, "leaguePoints": lp, "last_update": last_update}}
    )

    formatted_last_update = last_update.strftime("%H:%M")
    response_message = f"Victorias: {wins}, Derrotas: {losses} {league_status} | (Última Act.: {formatted_last_update})"
    return Response(response_message, mimetype='text/plain')

@summoner_bp.route('/', methods=['POST'])
def add_summoner():
    if not request.is_json:
        return Response("El cuerpo de la solicitud debe ser JSON", status=400, mimetype='text/plain')

    data = request.get_json()
    if not data:
        return Response("Datos no proporcionados", status=400, mimetype='text/plain')

    summoner_name = data.get('summoner_name')
    tagline = data.get('tagline')

    if not summoner_name or not tagline:
        return Response("Faltan datos", status=400, mimetype='text/plain')

    summoner_name = summoner_name.lower()
    tagline = tagline.lower()

    existing_summoner = summoners_collection.find_one({"summoner_name": summoner_name, "tagline": tagline})
    if existing_summoner:
        return Response("El invocador ya existe en la base de datos", status=400, mimetype='text/plain')

    summoner_info = get_summoner_info(summoner_name, tagline)
    if not summoner_info:
        return Response("No existe el invocador en la base de datos de riot", status=404, mimetype='text/plain')

    puuid = summoner_info['puuid']
    summoner_id_info = get_summoner_id(puuid)
    if not summoner_id_info or 'id' not in summoner_id_info:
        return Response("No se pudo obtener el ID del invocador", status=500, mimetype='text/plain')

    summoner_id = summoner_id_info['id']
    league_info = get_league_info(summoner_id)
    if league_info:
        league = league_info[0]['tier']
        rank = league_info[0]['rank']
        lp = league_info[0]['leaguePoints']
    else:
        league = None
        rank = None
        lp = None

    summoners_collection.insert_one({
        "summoner_name": summoner_name,
        "tagline": tagline,
        "puuid": puuid,
        "id": summoner_id,
        "wins": 0,
        "losses": 0,
        "tier": league,
        "rank": rank,
        "leaguePoints": lp,
        "last_update": datetime.now()
    })

    return Response("Invocador agregado exitosamente", status=201, mimetype='text/plain')
