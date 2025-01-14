import os
import requests
from flask import Blueprint, request, jsonify
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
        return jsonify({"error": "No existe el invocador en la base de datos"}), 404

    puuid = summoner['puuid']
    matches = get_matches(puuid)
    wins, losses = 0, 0
    data_obtained = True  # Variable para indicar si la obtención de datos fue exitosa

    # Tipos de partidas a contar
    # [400,   450,  420,      440] 
    # Normal, ARAM, Solo/Duo, Flex
    game_types_to_count = [420]
    

    for match_id in matches:
        match_details = get_match_details(match_id)
        if not match_details:
            print("ERROR | match_details No se han podido obtener desde la API de Riot.")
            data_obtained = False
            continue

        if 'info' not in match_details or 'participants' not in match_details['info']:
            print("ERROR | Estructura de datos inesperada en la respuesta de la API de Riot.")
            data_obtained = False
            continue

        game_duration = match_details['info'].get('gameDuration', 0)
        if game_duration < 300:  # Filtrar partidas "remake" (menos de 5 minutos)
            continue

        game_type = match_details['info'].get('queueId', None)
        if game_type not in game_types_to_count:
            continue

        for participant in match_details['info'].get('participants', []):
            if participant.get('puuid') == puuid:
                if participant.get('win'):
                    wins += 1
                else:
                    losses += 1
                break
            
    if data_obtained:
        print("EXITO | Se han obtenido los datos correctamente desde la API de Riot.")

        last_update = datetime.now(tz=chile_tz)
        update_result = summoners_collection.update_one(
            {"summoner_name": summoner_name, "tagline": tagline},
            {"$set": {"wins": wins, "losses": losses, "last_update": last_update}}
        )

        if update_result.modified_count > 0:
            print("EXITO | Los datos se han actualizado correctamente en la base de datos.")
        else:
            print("ERROR | No se han podido actualizar los datos en la base de datos.")

        formatted_last_update = last_update.strftime("%H:%M")
        response_message = f"Victorias: {wins}, Derrotas: {losses} (Actualizado a las {formatted_last_update})"
        
        if not data_obtained:
            response_message += " || Error con la API de Riot. ||"

        return jsonify(response_message)


@summoner_bp.route('/', methods=['POST'])
def add_summoner():
    if not request.is_json:
        return jsonify({"error": "El cuerpo de la solicitud debe ser JSON"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Datos no proporcionados"}), 400

    summoner_name = data.get('summoner_name')
    tagline = data.get('tagline')

    if not summoner_name or not tagline:
        return jsonify({"error": "Faltan datos"}), 400

    summoner_name = summoner_name.lower()
    tagline = tagline.lower()

    existing_summoner = summoners_collection.find_one({"summoner_name": summoner_name, "tagline": tagline})
    if existing_summoner:
        return jsonify({"error": "El invocador ya existe en la base de datos"}), 400

    summoner_info = get_summoner_info(summoner_name, tagline)
    if not summoner_info:
        return jsonify({"error": "No existe el invocador en la base de datos de riot"}), 404

    summoners_collection.insert_one({
        "summoner_name": summoner_name,
        "tagline": tagline,
        "puuid": summoner_info['puuid'],
        "wins": 0,
        "losses": 0,
        "last_update": datetime.now()
    })

    return jsonify({"Invocador agregado exitosamente"}), 201

#funcional 100%, este es un buen punto de retorno. Falta mejorar visuales y validaciones.
