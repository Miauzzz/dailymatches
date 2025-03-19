from flask import Flask
from gestionapi import summoner_bp, cache
import os  # Importa el módulo os para usar variables de entorno

app = Flask(__name__)
port = int(os.getenv("PORT", 3000))  # Asegúrate de convertir el puerto a entero

# Configuración de caché
app.config['CACHE_TYPE'] = 'simple'
cache.init_app(app)

# Registra el blueprint
app.register_blueprint(summoner_bp, url_prefix='/summoner')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)  # Usa debug=False en producción
