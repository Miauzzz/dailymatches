<div align="center">

# Daylimatches API

### API REST Para obtener las partidas diarias de jugadores de League of Legends

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=flat&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Retorna el historial diario de un summoner de league of legends (Actualmente solo de LAS)*

[Ver Demo](https://kick.com/madafocker) · [Reportar Bug](https://github.com/Miauzzz/dailymatches/issues)

Para la demo debes escribir en el chat !soloq
</div>

<div>
## README DESACTUALIZADO

## ✨ Características

- 📈 **Seguimiento automático** de victorias y derrotas diarias
- ⏰ **Reseteo automático** de estadísticas a las 4:00 AM (hora de Chile)
- 🏆 **Información de rangos** (Tier, División, LP) para SoloQ y FlexQ
- 💾 **Caché integrado** para optimizar consultas frecuentes
- 🔄 **Actualización en tiempo real** mediante la API de Riot Games
- 🌎 **Zona horaria de Chile** para sincronización diaria
- 📊 **Soporte para múltiples colas**: SoloQ (Ranked) y FlexQ


## 📦 Prerrequisitos

Antes de comenzar, asegúrate de tener instalado:
- **Python 3.8 o superior**
- **MongoDB**
- **API Key de Riot Games** ([Obtener aquí](https://developer.riotgames.com/))
- **pip** (gestor de paquetes de Python)
</div>

## 🚀 Instalación

### 1. Clona el repositorio

```bash
git clone https://github.com/Miauzzz/dailymatches.git
cd dailymatches
```

### 2. Crea un entorno virtual (recomendado)

```bash
python -m venv venv
```

# Windows
```powershell
\venv\Scripts\activate
```

# Linux/Mac
```bash
source venv/bin/activate
```

### 3. Instala las dependencias

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuración

### 1. Crea un archivo `.env` en la raíz del proyecto
```markdown
//API Key de Riot Games
RIOT_API_KEY= Aqui va tu api key de riot.

//Puerto de la aplicación (opcional, default: 3000)
PORT=3000

// Configuración de MongoDB
MONGO_URI= Aqui colocas el link proporcionado en mongodb
MONGO_DB= Aqui colocas el nombre de tu base de datos.
```

### 2. Configura MongoDB

Asegúrate de que MongoDB esté ejecutándose. Por defecto, la aplicación creará una colección llamada `summoners` en la base de datos especificada.

---

## 🔌 Endpoints

### Agregar un Summoner
Registra un nuevo invocador en la base de datos para comenzar a rastrear sus estadísticas.

```
POST /summoner/
Content-Type: application/json
```
```json
{
  "summoner_name": "Hide on bush",
  "tagline": "KR1"
}
```

**Respuestas:**
- `201` - Invocador agregado exitosamente
- `400` - Datos faltantes o invocador ya existe
- `404` - Invocador no encontrado en Riot

---

### Obtener Estadísticas Diarias

Consulta las victorias y derrotas del día actual (desde las 4:00 AM).

```
GET /summoner/{queue_type}/{summoner}/{tagline}
```

**Parámetros:**
- `queue_type`: Tipo de cola (`soloq` o `flexq`)
- `summoner`: Nombre del invocador (case-insensitive)
- `tagline`: Tagline del invocador (case-insensitive)

**Ejemplo:**
```
GET /summoner/soloq/hide%20on%20bush/KR1
```

**Respuestas:**
- `200` - Estadísticas obtenidas
- `400` - Tipo de cola inválido
- `404` - Invocador no existe en la base de datos

---

## 📄 Ejemplos de Respuesta

### POST `/summoner/` - Agregar Invocador

**Request:**
```bash
curl -X POST http://localhost:3000/summoner/ \
  -H "Content-Type: application/json" \
  -d '{
    "summoner_name": "Faker",
    "tagline": "KR1"
  }'
```

**Response (201):**
​```
Invocador agregado exitosamente
​```

---

### GET `/summoner/soloq/faker/kr1` - Obtener Estadísticas

**Request:**
​```
curl http://localhost:3000/summoner/soloq/faker/kr1
​```

**Response (200):**
```json
Victorias: 8 / Derrotas: 2 | CHALLENGER I (1247 LP) (Act. 14:30)
```

**Response (sin liga asignada):**
```json
Victorias: 5 / Derrotas: 3 | Y no tiene liga asignada (Act. 10:15)
```

---

## 📁 Estructura del Proyecto

```
dailymatches/
│
├── index.py              # Punto de entrada de la aplicación Flask
├── gestionapi.py         # Lógica principal de endpoints y procesamiento
├── db.py                 # Configuración de conexión a MongoDB
├── requirements.txt      # Dependencias del proyecto
├── .env                  # Variables de entorno (no incluido en repo)
└── README.md            # Documentación del proyecto
```

---

## 🔍 Detalles Técnicos

### Sistema de Reseteo Diario

La API resetea automáticamente las estadísticas a las **4:00 AM** (zona horaria de Chile) cada día. Esto significa:

- Si consultas antes de las 4 AM, se cuentan las partidas desde las 4 AM del día anterior
- Si consultas después de las 4 AM, se cuentan las partidas desde las 4 AM del día actual
- El contador se reinicia automáticamente al primer request después de las 4 AM (Para dar margen a los streams que duran hasta tarde).

### Sistema de Caché

- Las consultas GET se cachean por **60 segundos** para reducir la carga en la API de Riot
- El caché se invalida automáticamente después del tiempo configurado
- Útil para dashboards o bots que consultan frecuentemente

### Validación de Partidas

Solo se cuentan partidas que cumplan:
- Pertenecen a la cola especificada (SoloQ: 420, FlexQ: 440)
- Duración mínima de **5 minutos** (300 segundos)
- Jugadas en el período de tiempo válido (desde las 4 AM)


## 🙏 Agradecimientos

- A Madafocker por darme la oportunidad de incorporarlo en su Stream, siganlo en [KICK](https://kick.com/madafocker)💚
- [Riot Games API](https://developer.riotgames.com/) por proporcionar los datos
- [Flask](https://flask.palletsprojects.com/) por el excelente framework web
---

## 📝 Licencia

Distribuido bajo la licencia MIT. Ver `LICENSE` para más información.

---

<div align="center">
<h6>Hecho con 💚 por Miauzzz, deja un ⭐ si te sirve de ayuda!</h6>
</div>
