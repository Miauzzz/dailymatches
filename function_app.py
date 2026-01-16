import azure.functions as func
import logging
import json
import traceback

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- INTENTO DE CARGA DE TU LÓGICA ---
gestionapi = None
error_carga = None

try:
    import gestionapi
except Exception as e:
    # Si falla el import (por DB, librerías, sintaxis), guardamos el error
    error_carga = traceback.format_exc()


# --- RUTA 1: TU API (Si cargó bien) ---
@app.route(route="summoner/{queue_type}/{summoner}/{tagline}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_stats(req: func.HttpRequest) -> func.HttpResponse:
    # 1. Si hubo error al arrancar, mostrarlo aquí
    if error_carga:
        return func.HttpResponse(
            f"⛔ ERROR CRÍTICO AL INICIAR:\n\n{error_carga}", 
            status_code=500, 
            mimetype="text/plain"
        )

    # 2. Si cargó bien, ejecutar lógica normal
    try:
        queue_type = req.route_params.get('queue_type')
        summoner = req.route_params.get('summoner')
        tagline = req.route_params.get('tagline')

        resultado = gestionapi.logic_get_queue_stats(queue_type, summoner, tagline)
        
        if "error" in resultado:
            return func.HttpResponse(resultado["error"], status_code=resultado["status"])

        return func.HttpResponse(resultado["message"], status_code=200, mimetype="text/plain")

    except Exception as e:
        return func.HttpResponse(f"Error interno: {str(e)}", status_code=500)


# --- RUTA 2: AGREGAR SUMMONER (Si cargó bien) ---
@app.route(route="summoner", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def add_summoner(req: func.HttpRequest) -> func.HttpResponse:
    if error_carga:
        return func.HttpResponse(f"⛔ ERROR CRÍTICO:\n{error_carga}", status_code=500)

    try:
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse("JSON inválido", status_code=400)

        resultado = gestionapi.logic_add_summoner(req_body)
        return func.HttpResponse(resultado["message"], status_code=resultado["status"])

    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


# --- RUTA 3: TEST DE VIDA (Para ver si Azure respira) ---
@app.route(route="test", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def test_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    if error_carga:
        return func.HttpResponse(f"La app encendió pero con errores:\n{error_carga}", status_code=500)
    return func.HttpResponse("¡La API está viva y gestionapi se importó correctamente!", status_code=200)
