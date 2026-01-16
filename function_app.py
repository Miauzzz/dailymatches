import azure.functions as func
import sys
import traceback # Para ver el detalle del error
from io import BytesIO

class WsgiMiddleware:
    def __init__(self, app):
        self.app = app

    def handle(self, req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
        headers = {k: v for k, v in req.headers.items()}
        environ = {
            'REQUEST_METHOD': req.method,
            'SCRIPT_NAME': '',
            'PATH_INFO': req.route_params.get('route', '/'),
            'QUERY_STRING': req.url.split('?', 1)[1] if '?' in req.url else '',
            'SERVER_NAME': 'azure_function',
            'SERVER_PORT': '80',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'https',
            'wsgi.input': BytesIO(req.get_body()),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }
        environ.update({f'HTTP_{k.upper().replace("-", "_")}': v for k, v in headers.items()})
        environ['CONTENT_LENGTH'] = str(len(req.get_body()))
        environ['CONTENT_TYPE'] = headers.get('Content-Type', '')

        status_response = []
        headers_response = []
        response_body = []

        def start_response(status, headers, exc_info=None):
            status_response.append(status)
            headers_response.append(headers)
            return response_body.append

        app_iter = self.app(environ, start_response)
        try:
            for data in app_iter:
                response_body.append(data)
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()

        if not status_response:
            return func.HttpResponse("Error interno: Flask no devolvió respuesta.", status_code=500)

        status_code = int(status_response[0].split(' ')[0])
        body = b''.join(response_body)
        
        return func.HttpResponse(
            body=body,
            status_code=status_code,
            headers=dict(headers_response[0]),
            mimetype=dict(headers_response[0]).get('Content-Type', 'text/plain')
        )

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# --- ZONA DE TRAMPA DE ERRORES ---
wsgi_app = None
error_de_carga = None

try:
    from index import app as flask_app
    wsgi_app = WsgiMiddleware(flask_app.wsgi_app)

except Exception as e:
    error_de_carga = f"ERROR AL INICIAR FLASK:\n{str(e)}\n\n{traceback.format_exc()}"


@app.route(route="{*route}", auth_level=func.AuthLevel.ANONYMOUS)
def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    if error_de_carga:
        return func.HttpResponse(
            error_de_carga,
            status_code=500,
            mimetype="text/plain"
        )
    
    if wsgi_app is None:
        return func.HttpResponse(
            "Error desconocido: La app no se inicializó correctamente.",
            status_code=500
        )

    return wsgi_app.handle(req, context)
