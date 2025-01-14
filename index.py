from flask import Flask
from gestionapi import summoner_bp, cache

app = Flask(__name__)

# Configuración de caché
app.config['CACHE_TYPE'] = 'simple'
cache.init_app(app)

app.register_blueprint(summoner_bp, url_prefix='/summoner')

if __name__ == '__main__':
    app.run(debug=True)
