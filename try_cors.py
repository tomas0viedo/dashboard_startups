from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

app = Flask(__name__)
# Habilita CORS para todas las rutas. En producción, restringe a orígenes específicos.
CORS(app) 

load_dotenv()

# --- CONFIGURACIÓN DE TU BASE DE DATOS ---
MONGO_URI = os.getenv('DATABASE_URL', 'mongodb+srv://maxiesco:maxiesco@cluster0.3zdo3lp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
DB_NAME = 'Cluster0'
COLLECTION_NAME = 'sessions'

# --- Conexión a MongoDB ---
def get_mongo_collection():
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        client.admin.command('ping') 
        print("✅ Conectado a MongoDB Atlas para Web Service.")
        return db[COLLECTION_NAME]
    except Exception as e:
        print(f"❌ Error al conectar a MongoDB Atlas: {e}")
        return None

sessions_collection = get_mongo_collection()

# --- Endpoints de tu Web Service ---

@app.route('/')
def home():
    return "Web Service de Sesiones funcionando. Visita /api/v1/sessions para ver datos."

@app.route('/api/v1/sessions', methods=['GET'])
def get_sessions():
    """Retorna todas las sesiones."""
    if sessions_collection is None:
        return jsonify({"error": "Base de datos no conectada."}), 500
    
    sessions = []
    for s in sessions_collection.find({}):
        # Convierte ObjectId y datetime a string para JSON
        s['_id'] = str(s['_id'])
        if 'mentor' in s and isinstance(s['mentor'], ObjectId):
            s['mentor'] = str(s['mentor'])
        if 'startup' in s and isinstance(s['startup'], ObjectId):
            s['startup'] = str(s['startup'])
        if 'date' in s and isinstance(s['date'], datetime):
            s['date'] = s['date'].isoformat()
        if 'dateTime' in s and isinstance(s['dateTime'], datetime):
            s['dateTime'] = s['dateTime'].isoformat()
        if 'mentorSigned' in s and 'timestamp' in s['mentorSigned'] and isinstance(s['mentorSigned']['timestamp'], datetime):
            s['mentorSigned']['timestamp'] = s['mentorSigned']['timestamp'].isoformat()
        if 'startupSigned' in s and 'timestamp' in s['startupSigned'] and isinstance(s['startupSigned']['timestamp'], datetime):
            s['startupSigned']['timestamp'] = s['startupSigned']['timestamp'].isoformat()
        
        sessions.append(s)
    return jsonify(sessions)

# Puedes añadir un endpoint para el "seeder" si quieres ejecutarlo vía HTTP (no recomendado para producción así)
@app.route('/api/v1/seed_sessions', methods=['POST'])
def seed_sessions_api():
    """Inserta documentos de prueba en la colección 'sessions' via API."""
    if sessions_collection is None:
        return jsonify({"error": "Base de datos no conectada."}), 500
    
    # Este código debería ser manejado con más cuidado en una API real (seguridad, idempotencia)
    # Por simplicidad, tomamos los IDs de ejemplo de tu código anterior.
    mentor_id_ejemplo_1 = ObjectId("687dbc64a09e6c626f1bc7e4")
    startup_id_ejemplo_1 = ObjectId("687dbba6a09e6c626f1bc7e3")
    mentor_id_ejemplo_2 = ObjectId("687dbc7ba09e6c626f1bc7e5")
    startup_id_ejemplo_2 = ObjectId("687dbc94a09e6c626f1bc7e6")

    sessions_to_insert = [
        {
            "mentor": mentor_id_ejemplo_1,
            "startup": startup_id_ejemplo_1,
            "date": datetime(2025, 7, 28, 10, 0, 0),
            "dateTime": datetime(2025, 7, 28, 10, 0, 0),
            "duration": 1.0,
            "topic": "Diseño de la Propuesta de Valor",
            "summary": "Sesión inicial para definir el valor principal de la startup.",
            "mentorSigned": {"signed": False},
            "startupSigned": {"signed": False},
            "status": "pending",
            "comments": ["Foco en cliente potencial."],
            "pdfUrl": ""
        },
        {
            "mentor": mentor_id_ejemplo_2,
            "startup": startup_id_ejemplo_2,
            "date": datetime(2025, 8, 10, 14, 0, 0),
            "dateTime": datetime(2025, 8, 10, 14, 0, 0),
            "duration": 1.0,
            "topic": "Estrategias de Crecimiento y Escalado",
            "summary": "Discusión sobre próximos pasos para escalar el negocio.",
            "mentorSigned": {"signed": True, "timestamp": datetime.now()},
            "startupSigned": {"signed": True, "timestamp": datetime.now()},
            "status": "signed",
            "comments": ["Revisar métricas de usuario."],
            "pdfUrl": "http://tuempresa.com/informe_crecimiento.pdf"
        },
    ]
    
    try:
        result = sessions_collection.insert_many(sessions_to_insert)
        return jsonify({"message": f"Documentos insertados correctamente. IDs: {[str(id) for id in result.inserted_ids]}"}), 201
    except Exception as e:
        return jsonify({"error": f"Error al insertar documentos: {str(e)}"}), 500

if __name__ == '__main__':
    # Usa el puerto que Render asigna o 5000 por defecto para local
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))