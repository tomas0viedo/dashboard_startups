import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import pandas as pd
import plotly.express as px
from datetime import datetime
from bson.objectid import ObjectId
import io

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Dashboard de Startups y Sesiones",
                    initial_sidebar_state="collapsed") 

# --- CSS Mínimo para Fuente Helvetica y Legibilidad de Tablas ---
st.markdown(
    """
    <style>
    /* Aplica la fuente Helvetica a todo el cuerpo de la aplicación */
    body {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }

    /* Estilos para las tablas (DataFrames) de Streamlit para asegurar legibilidad */
    .stDataFrame th, .stDataFrame td {
        color: var(--text-color, #334155); /* Usa la variable de Streamlit o un color oscuro */
        background-color: var(--secondary-background-color, #ffffff); /* Usa la variable de Streamlit o blanco */
    }
    .stDataFrame th {
        background-color: var(--background-color, #f1f5f9); /* Usa la variable de Streamlit o un gris claro */
        color: var(--text-color, #475569); /* Color de texto oscuro para cabeceras */
    }
    </style>
    """,
    unsafe_allow_html=True
)

load_dotenv()

# --- Conexión a MongoDB Atlas ---
@st.cache_resource(ttl=3600)
def init_connection():
    try:
        mongo_url = os.getenv("DATABASE_URL")
        if not mongo_url:
            st.warning("DATABASE_URL no encontrada en .env, usando la URL hardcodeada.")
            mongo_url = "mongodb+srv://maxiesco:maxiesco@cluster0.3zdo3lp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        
        client = MongoClient(mongo_url, server_api=ServerApi('1'))
        client.admin.command('ping') 
        return client["Cluster0"]
    except Exception as e:
        st.error("Por favor, verifica tu cadena de conexión (DATABASE_URL) y la configuración del acceso a la red en MongoDB Atlas.")
        return None

db = init_connection()

# --- Obtener Colecciones ---
startups_collection = db["startup"] if db is not None else None
mentors_collection = db["mentorship"] if db is not None else None 
sessions_collection = db["sessions"] if db is not None else None

# --- Funciones Auxiliares para Datos ---
def serialize_doc(doc):
    """Convierte ObjectId y datetime a string para JSON-like display."""
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, dict):
            doc[key] = serialize_doc(value)
    return doc

def get_data(collection):
    if collection is None:
        return []
    data = list(collection.find({}))
    return [serialize_doc(doc) for doc in data]

@st.cache_data(ttl=300)
def get_sessions_with_details():
    if sessions_collection is None or mentors_collection is None or startups_collection is None:
        st.error("Colección de sesiones, mentores o startups no disponible para detalles.")
        return []
    
    pipeline = [
        {"$addFields": {
            "mentorObjectId": {
                "$cond": {
                    "if": {"$and": [{"$ne": [{"$type": "$mentor"}, "objectId"]}, {"$ne": ["$mentor", None]}]},
                    "then": {"$convert": {"input": "$mentor", "to": "objectId", "onError": None, "onNull": None}},
                    "else": "$mentor"
                }
            }
        }},
        {"$lookup": {
            "from": "mentorship", # Colección de mentores
            "localField": "mentorObjectId", # Usamos el campo convertido a ObjectId
            "foreignField": "_id",
            "as": "mentor_info"
        }},
        {"$unwind": {"path": "$mentor_info", "preserveNullAndEmptyArrays": True}},
        
        # Unir con la colección de startups
        {"$lookup": {
            "from": "startup",
            "localField": "startup",
            "foreignField": "_id",
            "as": "startup_info"
        }},
        {"$unwind": {"path": "$startup_info", "preserveNullAndEmptyArrays": True}},
        
        {"$project": {
            "_id": {"$toString": "$_id"},
            "mentor_id": {"$toString": {"$ifNull": ["$mentor_info._id", None]}},
            "Company Name": {"$ifNull": ["$mentor_info.company", "Compañía Desconocida"]}, 
            "startup_id": {"$toString": {"$ifNull": ["$startup_info._id", None]}},
            "startup_company": {"$ifNull": ["$startup_info.name", "$startup_info.company", "Startup Desconocida"]},
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M", "date": "$date"}},
            "topic": "$topic",
            "duration": "$duration",
            "summary": "$summary",
            "status": "$status",
            "comments": {"$ifNull": ["$comments", []]},
            "pdfUrl": {"$ifNull": ["$pdfUrl", ""]},
            "mentorSigned": "$mentorSigned",
            "startupSigned": "$startupSigned",
        }},
        {"$sort": {"date": -1}}
    ]
    
    try:
        data = list(sessions_collection.aggregate(pipeline))
        return data
    except Exception as e:
        st.error(f"Error al ejecutar la agregación de sesiones: {e}")
        return []


# --- Interfaz del Dashboard  ---
st.title("📊 Dashboard de Gestión de Startups y Sesiones")

if db is None:
    st.info("Por favor, soluciona el problema de conexión a la base de datos para acceder al dashboard.")
else:
    # Envuelve todo el contenido del dashboard en un contenedor principal
    with st.container():
        # Cargar todos los datos necesarios al inicio
        startups = get_data(startups_collection)
        mentors = get_data(mentors_collection) 
        sessions_detailed = get_sessions_with_details()

        ## Resumen General
        st.header("Resumen General")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Startups", len(startups))
        with col2:
            st.metric("Total Mentores", len(mentors))
        with col3:
            signed_sessions_count = sum(1 for s in sessions_detailed if s.get('status') == 'signed')
            st.metric("Sesiones Firmadas", signed_sessions_count)
        
        st.markdown("---")

        ## Distribución de Startups por Sector
        st.subheader("Distribución de Startups por Sector 📈")
        if startups:
            df_startups = pd.DataFrame(startups)
            sector_counts = df_startups['sector'].value_counts().reset_index()
            sector_counts.columns = ['Sector', 'Cantidad']
            top_n_sectors = 8 
            if len(sector_counts) > top_n_sectors:
                top_sectors = sector_counts.head(top_n_sectors - 1)
                other_count = sector_counts.iloc[top_n_sectors-1:]['Cantidad'].sum()
                if other_count > 0:
                    others_df = pd.DataFrame([{"Sector": "Otros", "Cantidad": other_count}])
                    sector_counts = pd.concat([top_sectors, others_df]).sort_values(by="Cantidad", ascending=False)
                else:
                    sector_counts = top_sectors
            
            fig_sector = px.pie(sector_counts, values='Cantidad', names='Sector', title='Distribución por Sector de Startups', hole=0.3, template='plotly_white')
            st.plotly_chart(fig_sector, use_container_width=True)
        else:
            st.info("No hay datos de startups para el gráfico de sectores.")

        st.markdown("---")

        ## Distribución de Startups por Etapa con detalle
        st.subheader("Distribución de Startups por Etapa 🚀")
        if startups:
            df_startups = pd.DataFrame(startups)
            stage_counts = df_startups['stage'].value_counts().reset_index()
            stage_counts.columns = ['Etapa', 'Cantidad']
            fig_stage = px.bar(stage_counts, x='Etapa', y='Cantidad', title='Conteo de Startups por Etapa',
                                color='Etapa', text='Cantidad', template='plotly_white')
            st.plotly_chart(fig_stage, use_container_width=True)
            
            # Detalle de Startups por Etapa
            st.markdown("#### Detalle de Startups por Etapa")
            selected_stage = st.selectbox("Selecciona una Etapa para ver las Startups:", 
                                            options=['Todas'] + (list(stage_counts['Etapa'].unique()) if not stage_counts.empty else []),
                                            key='stage_select')
            
            if selected_stage == 'Todas':
                filtered_startups_by_stage = startups
            else:
                filtered_startups_by_stage = [s for s in startups if s.get('stage') == selected_stage]
            
            if filtered_startups_by_stage:
                processed_startups = []
                for s in filtered_startups_by_stage:
                    processed_startups.append({
                        'Compañía': s.get('company', 'N/A'),
                        'Sector': s.get('sector', 'N/A'),
                        'Etapa': s.get('stage', 'N/A'),
                        'Persona de Contacto': s.get('contact', s.get('contactPerson', 'N/A')),
                        'Email': s.get('email', 'N/A'),           
                        'Sitio Web': s.get('website', 'N/A')         
                    })
                df_filtered_startups = pd.DataFrame(processed_startups)
                st.dataframe(df_filtered_startups, use_container_width=True) 
            else:
                st.info("No hay startups en esta etapa para mostrar.")
        else:
            st.info("No hay datos de startups para el gráfico de etapas.")
        
        st.markdown("---")

        ## Estado Actual de las Sesiones con detalle
        st.subheader("Estado Actual de las Sesiones 📊")
        if sessions_detailed:
            df_sessions = pd.DataFrame(sessions_detailed)
            status_counts = df_sessions['status'].value_counts().reset_index()
            status_counts.columns = ['Estado', 'Cantidad']
            fig_status = px.bar(status_counts, x='Estado', y='Cantidad', title='Conteo de Sesiones por Estado',
                                 color='Estado', text='Cantidad', template='plotly_white')
            st.plotly_chart(fig_status, use_container_width=True)

            # Detalle de Sesiones por Estado
            st.markdown("#### Detalle de Sesiones por Estado")
            selected_status = st.selectbox("Selecciona un Estado para ver las Sesiones:", 
                                            options=['Todas'] + (list(status_counts['Estado'].unique()) if not status_counts.empty else []), 
                                            key='session_status_select')
            
            if selected_status == 'Todas':
                filtered_sessions_by_status = sessions_detailed
            else:
                filtered_sessions_by_status = [s for s in sessions_detailed if s.get('status') == selected_status]
            
            if filtered_sessions_by_status:
                df_filtered_sessions = pd.DataFrame(filtered_sessions_by_status)

                df_display_detail = df_filtered_sessions.rename(columns={
                    "date": "Fecha",
                    "Company Name": "Compañía Mentor",
                    "startup_company": "Compañía Startup",
                    "topic": "Tema",
                    "status": "Estado",
                    "summary": "Resumen",
                    "comments": "Comentarios"
                })
                col_order_detail = ["Fecha", "Compañía Mentor", "Compañía Startup", "Tema", "Estado", "Resumen", "Comentarios"]
                df_display_detail = df_display_detail.reindex(columns=[col for col in col_order_detail if col in df_display_detail.columns])
                st.dataframe(df_display_detail, use_container_width=True)
            else:
                st.info("No hay sesiones con este estado para mostrar.")
        else:
            st.info("No hay datos de sesiones para el gráfico de estado.")

        st.markdown("---")

        ## Gestión y Descarga de Sesiones Detalladas
        st.header("Gestión y Descarga de Sesiones Detalladas")
        st.write("Explora y descarga todas las sesiones con los nombres del mentor y la startup.")
        
        if sessions_detailed:
            df_sessions_full = pd.DataFrame(sessions_detailed)

            df_display_download = df_sessions_full.rename(columns={
                "date": "Fecha",
                "Company Name": "Compañía Mentor",
                "startup_company": "Compañía Startup",
                "topic": "Tema",
                "status": "Estado",
                "summary": "Resumen",
                "duration": "Duración",
                "comments": "Comentarios",
                "pdfUrl": "URL PDF",
                "mentorSigned": "Mentor Firmó",
                "startupSigned": "Startup Firmó"
            })

            col_order_download = ["Fecha", "Compañía Mentor", "Compañía Startup", "Tema", "Estado", "Resumen", "Duración", "Comentarios", "URL PDF", "Mentor Firmó", "Startup Firmó"]
            df_display_download = df_display_download.reindex(columns=[col for col in col_order_download if col in df_display_download.columns])
            
            st.dataframe(df_display_download, use_container_width=True)
            
            excel_buffer = io.BytesIO()
            df_display_download.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0) 
            
            st.download_button(
                label="Descargar todas las Sesiones (Excel)",
                data=excel_buffer,
                file_name="all_sessions_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No hay sesiones registradas para mostrar o descargar.")