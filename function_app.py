import azure.functions as func
import logging
import json
import gestionapi # Importamos tu lógica limpia

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- RUTA 1: GET STATISTICS ---
# URL: /api/summoner/{queue_type}/{summoner}/{tagline}
@app.route(route="summoner/{queue_type}/{summoner}/{tagline}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_stats(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Procesando solicitud de estadísticas.')

    # 1. Obtener parámetros de la ruta
    queue_type = req.route_params.get('queue_type')
    summoner = req.route_params.get('summoner')
    tagline = req.route_params.get('tagline')

    try:
        # 2. Llamar a la lógica
        resultado = gestionapi.logic_get_queue_stats(queue_type, summoner, tagline)
        
        # 3. Verificar si hubo error en la lógica
        if "error" in resultado:
            return func.HttpResponse(resultado["error"], status_code=resultado["status"])

        # 4. Éxito: Devolver el texto plano (Como le gusta a tu bot)
        return func.HttpResponse(
            resultado["message"],
            status_code=200,
            mimetype="text/plain"
        )

    except Exception as e:
        logging.error(f"Error fatal: {str(e)}")
        return func.HttpResponse(f"Error interno del servidor: {str(e)}", status_code=500)


# --- RUTA 2: ADD SUMMONER ---
# URL: /api/summoner
@app.route(route="summoner", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def add_summoner(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Procesando solicitud para agregar summoner.')

    try:
        # 1. Obtener el JSON del cuerpo
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse("El cuerpo debe ser un JSON válido", status_code=400)

        # 2. Llamar a la lógica
        resultado = gestionapi.logic_add_summoner(req_body)

        # 3. Responder
        return func.HttpResponse(
            resultado["message"],
            status_code=resultado["status"],
            mimetype="text/plain"
        )

    except Exception as e:
        logging.error(f"Error fatal: {str(e)}")
        return func.HttpResponse(f"Error al agregar: {str(e)}", status_code=500)
