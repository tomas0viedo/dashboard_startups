from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from pymongo.server_api import ServerApi # Importa ServerApi
from bson import ObjectId
from dotenv import load_dotenv
import os
from typing import List, Dict, Any

# No necesitamos uvicorn aquí si vamos a usar un comando Docker para iniciarlo.
# import uvicorn

load_dotenv()

app = FastAPI(title="Startups Dashboard API",
              description="API para obtener datos de startups para visualizaciones.")

# CORS para permitir llamadas desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción ajusta dominio(s) específico(s)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión MongoDB
client = None
db = None
startups_collection = None

@app.on_event("startup")
def startup_db_client():
    global client, db, startups_collection
    mongo_url = os.getenv("DATABASE_URL")
    if not mongo_url:
        raise RuntimeError("DATABASE_URL no configurada. Asegúrate de que esté en el .env")
    
    try:
        # Conectamos con ServerApi('1') como lo hiciste en Streamlit
        client = MongoClient(mongo_url, server_api=ServerApi('1'))
        db = client["Cluster0"]
        startups_collection = db["startup"]
        
        # Prueba la conexión
        client.admin.command('ping') 
        print("✅ Conectado a MongoDB Atlas.")
    except Exception as e:
        print(f"❌ Error al conectar a MongoDB Atlas: {e}")
        # Puedes decidir si quieres que la aplicación falle al iniciar o intentar arrancar sin DB
        raise HTTPException(status_code=500, detail=f"No se pudo conectar a la base de datos: {e}")

@app.on_event("shutdown")
def shutdown_db_client():
    if client:
        client.close()
        print("👋 Conexión a MongoDB cerrada.")

@app.get("/", response_class=HTMLResponse, tags=["Raíz"])
def get_home():
    # En un entorno de API, esta ruta principal puede ser una página de documentación simple
    # o un mensaje de bienvenida. No servirá el HTML del dashboard aquí.
    return "<h1>API de Startups funcionando</h1><p>Visita /docs para la documentación de la API.</p>"


# Endpoints para los datos de los gráficos y tablas

@app.get("/api/startups/awards-by-sector", tags=["Gráficos y Datos"])
def awards_by_sector():
    # Asegúrate de que la colección está disponible
    if startups_collection is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    
    pipeline = [
        {"$addFields": {
            "awardsInt": {
                "$convert": {
                    "input": "$awards",
                    "to": "int",
                    "onError": 0,
                    "onNull": 0
                }
            }
        }},
        {"$match": {"awardsInt": {"$ne": None}}}, # Nos aseguramos de que awardsInt no sea nulo (aunque onError/onNull ya lo previenen)
        {"$group": {"_id": "$sector", "total_awards": {"$sum": "$awardsInt"}}},
        {"$sort": {"total_awards": -1}}
    ]
    try:
        result = list(startups_collection.aggregate(pipeline))
        data = [{"sector": doc["_id"] or "Otros", "total_awards": doc["total_awards"]} for doc in result]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener premios por sector: {e}")


@app.get("/api/startups/contact-web-status", tags=["Gráficos y Datos"])
def contact_web_status():
    if startups_collection is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    try:
        with_contact = startups_collection.count_documents({"contactPerson": {"$exists": True, "$ne": None, "$ne": ""}})
        without_contact = startups_collection.count_documents({"$or": [{"contactPerson": {"$exists": False}}, {"contactPerson": None}, {"contactPerson": ""}]})
        with_website = startups_collection.count_documents({"website": {"$exists": True, "$ne": None, "$ne": ""}})
        without_website = startups_collection.count_documents({"$or": [{"website": {"$exists": False}}, {"website": None}, {"website": ""}]})

        return [
            {"status": "Con contacto", "count": with_contact},
            {"status": "Sin contacto", "count": without_contact},
            {"status": "Con web", "count": with_website},
            {"status": "Sin web", "count": without_website}
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado de contacto y web: {e}")


@app.get("/api/startups/sector-distribution", tags=["Gráficos y Datos"])
def sector_distribution():
    if startups_collection is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    try:
        pipeline = [
            {"$group": {
                "_id": "$sector",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        result = list(startups_collection.aggregate(pipeline))
        data = [{"sector": doc["_id"] or "Otros", "count": doc["count"]} for doc in result]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener distribución de sectores: {e}")


@app.get("/api/startups/top-awards", tags=["Gráficos y Datos"])
def top_awards():
    if startups_collection is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    try:
        pipeline = [
            {"$addFields": {
                "awardsInt": {
                    "$convert": {
                        "input": "$awards",
                        "to": "int",
                        "onError": 0,
                        "onNull": 0
                    }
                }
            }},
            {"$sort": {"awardsInt": -1}},
            {"$limit": 5},
            {"$project": {"company": 1, "awards": "$awardsInt", "_id": 0}}
        ]
        result = list(startups_collection.aggregate(pipeline))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener top premios: {e}")


@app.get("/api/startups/contacts", tags=["Tablas y Listados"])
def contacts_list():
    if startups_collection is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    try:
        cursor = startups_collection.find(
            {"contactPerson": {"$ne": None, "$ne": ""}},
            {"company": 1, "contactPerson": 1, "email": 1, "sector": 1, "_id": 0}
        )
        return list(cursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener lista de contactos: {e}")

