from flask import Flask
from gestionapi import summoner_bp, cache
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
from db import summoners_collection

app = Flask(__name__)

# Configuración de caché
app.config['CACHE_TYPE'] = 'simple'
cache.init_app(app)

app.register_blueprint(summoner_bp, url_prefix='/summoner')

def reset_wins_losses():
    chile_tz = pytz.timezone('America/Santiago')
    now = datetime.now(chile_tz)
    if now.hour == 0 and now.minute == 0:
        summoners_collection.update_many({}, {"$set": {"wins": 0, "losses": 0}})
        print("Contadores de victorias y derrotas restablecidos a 0.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=reset_wins_losses, trigger="interval", minutes=1)
scheduler.start()

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
