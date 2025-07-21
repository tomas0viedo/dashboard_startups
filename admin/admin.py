import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import pandas as pd
import altair as alt
import plotly.express as px
from datetime import datetime
from bson.objectid import ObjectId

st.set_page_config(layout="wide", page_title="Dashboard de Startups y Sesiones")
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
        st.success("✅ Conectado a MongoDB Atlas para el Dashboard.")
        return client["Cluster0"]
    except Exception as e:
        st.error(f"❌ Error al conectar a MongoDB Atlas: {e}")
        st.error("Por favor, verifica tu cadena de conexión (DATABASE_URL) y la configuración del acceso a la red en MongoDB Atlas.")
        return None

db = init_connection()

# --- Obtener Colecciones ---
startups_collection = db["startup"] if db is not None else None
mentors_collection = db["mentors"] if db is not None else None
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
        {"$lookup": {
            "from": "mentors",
            "localField": "mentor",
            "foreignField": "_id",
            "as": "mentor_info"
        }},
        {"$unwind": {"path": "$mentor_info", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {
            "from": "startup",
            "localField": "startup",
            "foreignField": "_id",
            "as": "startup_info"
        }},
        {"$unwind": {"path": "$startup_info", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": {"$toString": "$_id"},
            "mentor_name": "$mentor_info.name",
            "startup_company": "$startup_info.company",
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M", "date": "$date"}},
            "topic": "$topic",
            "duration": "$duration",
            "summary": "$summary",
            "status": "$status",
            "comments": {"$ifNull": ["$comments", ""]},
            "pdfUrl": {"$ifNull": ["$pdfUrl", ""]},
            "mentorSigned": "$mentorSigned",
            "startupSigned": "$startupSigned",
        }},
        {"$sort": {"date": -1}}
    ]
    data = list(sessions_collection.aggregate(pipeline))
    return data

# --- Interfaz del Dashboard (Una Sola Página) ---
st.title("📊 Dashboard de Gestión de Startups y Sesiones")

if db is None:
    st.info("Por favor, soluciona el problema de conexión a la base de datos para acceder al dashboard.")
else:
    # Cargar todos los datos necesarios al inicio
    startups = get_data(startups_collection)
    mentors = get_data(mentors_collection) 
    sessions = get_sessions_with_details()

    st.header("Resumen General")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Startups", len(startups))
    with col2:
        st.metric("Total Mentores", len(mentors))
    with col3:
        signed_sessions = sum(1 for s in sessions if s.get('status') == 'signed')
        st.metric("Sesiones Firmadas", signed_sessions)
    
    st.markdown("---")

    # --- Distribución de Startups por Sector ---
    st.subheader("Distribución de Startups por Sector 📈")
    if startups:
        df_startups = pd.DataFrame(startups)
        sector_counts = df_startups['sector'].value_counts().reset_index()
        sector_counts.columns = ['Sector', 'Count']
        top_n_sectors = 8 
        if len(sector_counts) > top_n_sectors:
            top_sectors = sector_counts.head(top_n_sectors - 1)
            other_count = sector_counts.iloc[top_n_sectors-1:]['Count'].sum()
            if other_count > 0:
                others_df = pd.DataFrame([{"Sector": "Otros", "Count": other_count}])
                sector_counts = pd.concat([top_sectors, others_df]).sort_values(by="Count", ascending=False)
            else:
                sector_counts = top_sectors
        
        fig_sector = px.pie(sector_counts, values='Count', names='Sector', title='Distribución por Sector de Startups', hole=0.3)
        st.plotly_chart(fig_sector, use_container_width=True)
    else:
        st.info("No hay datos de startups para el gráfico de sectores.")

    st.markdown("---")

    # --- Distribución de Startups por Etapa con detalle ---
    st.subheader("Distribución de Startups por Etapa 🚀")
    if startups:
        df_startups = pd.DataFrame(startups)
        stage_counts = df_startups['stage'].value_counts().reset_index()
        stage_counts.columns = ['Etapa', 'Count']
        fig_stage = px.bar(stage_counts, x='Etapa', y='Count', title='Conteo de Startups por Etapa',
                           color='Etapa', text='Count')
        st.plotly_chart(fig_stage, use_container_width=True)
        
        # Detalle de Startups por Etapa
        st.markdown("#### Detalle de Startups por Etapa")
        selected_stage = st.selectbox("Selecciona una Etapa para ver las Startups:", 
                                      options=['Todas'] + list(stage_counts['Etapa'].unique()), 
                                      key='stage_select')
        
        if selected_stage == 'Todas':
            filtered_startups_by_stage = startups
        else:
            filtered_startups_by_stage = [s for s in startups if s.get('stage') == selected_stage]
        
        if filtered_startups_by_stage:
            # CORRECCIÓN PARA KEYERROR Y CAMPO 'contact'
            processed_startups = []
            for s in filtered_startups_by_stage:
                processed_startups.append({
                    'company': s.get('company', 'N/A'),
                    'sector': s.get('sector', 'N/A'),
                    'stage': s.get('stage', 'N/A'),
                    'contactPerson': s.get('contact', s.get('contactPerson', 'N/A')), # Prioriza 'contact', luego 'contactPerson'
                    'email': s.get('email', 'N/A'),           
                    'website': s.get('website', 'N/A')         
                })
            df_filtered_startups = pd.DataFrame(processed_startups)
            st.dataframe(df_filtered_startups, use_container_width=True) 
        else:
            st.info("No hay startups en esta etapa para mostrar.")
    else:
        st.info("No hay datos de startups para el gráfico de etapas.")
    
    st.markdown("---")

    # --- Estado Actual de las Sesiones con detalle ---
    st.subheader("Estado Actual de las Sesiones 📊")
    if sessions:
        df_sessions = pd.DataFrame(sessions)
        status_counts = df_sessions['status'].value_counts().reset_index()
        status_counts.columns = ['Estado', 'Count']
        fig_status = px.bar(status_counts, x='Estado', y='Count', title='Conteo de Sesiones por Estado',
                            color='Estado', text='Count')
        st.plotly_chart(fig_status, use_container_width=True)

        # Detalle de Sesiones por Estado
        st.markdown("#### Detalle de Sesiones por Estado")
        selected_status = st.selectbox("Selecciona un Estado para ver las Sesiones:", 
                                       options=['Todas'] + list(status_counts['Estado'].unique()), 
                                       key='session_status_select')
        
        if selected_status == 'Todas':
            filtered_sessions_by_status = sessions
        else:
            filtered_sessions_by_status = [s for s in sessions if s.get('status') == selected_status]
        
        if filtered_sessions_by_status:
            df_filtered_sessions = pd.DataFrame(filtered_sessions_by_status)
            col_order_detail = ["date", "mentor_name", "startup_company", "topic", "status", "summary", "comments"]
            df_display_detail = df_filtered_sessions.reindex(columns=[col for col in col_order_detail if col in df_filtered_sessions.columns])
            st.dataframe(df_display_detail, use_container_width=True)
        else:
            st.info("No hay sesiones con este estado para mostrar.")
    else:
        st.info("No hay datos de sesiones para el gráfico de estado.")

    st.markdown("---")

    # --- Listado de Contactos (CORREGIDO) ---
    st.header("Listado de Contactos de Startups")
    # Usa 'contact' primero, luego 'contactPerson', y filtra por campos no vacíos
    contacts_data = [
        s for s in startups 
        if s.get('contact', s.get('contactPerson')) not in [None, ""] # Verifica si 'contact' o 'contactPerson' tienen valor
    ]
    if contacts_data:
        # Crea el DataFrame con el campo 'contactPerson' que ahora maneja 'contact' o 'contactPerson'
        df_contacts_processed = []
        for s in contacts_data:
            df_contacts_processed.append({
                'company': s.get('company', 'N/A'),
                'contactPerson': s.get('contact', s.get('contactPerson', 'N/A')), # Usa la misma lógica
                'email': s.get('email', 'N/A'),
                'sector': s.get('sector', 'N/A'),
                'website': s.get('website', 'N/A')
            })
        df_contacts = pd.DataFrame(df_contacts_processed)
        st.dataframe(df_contacts[['company', 'contactPerson', 'email', 'sector', 'website']], use_container_width=True)
    else:
        st.info("No hay contactos de startups para mostrar.")

    st.markdown("---")

    # --- Gestión de Sesiones (tabla, siempre visible) ---
    st.header("Gestión y Descarga de Sesiones Detalladas")
    st.write("Explora y descarga todas las sesiones con los nombres del mentor y la startup.")
    
    if sessions:
        df_sessions_full = pd.DataFrame(sessions)
        col_order_download = ["_id", "date", "mentor_name", "startup_company", "topic", "status", "summary", "duration", "comments", "pdfUrl", "mentorSigned", "startupSigned"]
        df_display_download = df_sessions_full.reindex(columns=[col for col in col_order_download if col in df_sessions_full.columns])
        
        st.dataframe(df_display_download, use_container_width=True)
        st.download_button(
            label="Descargar todas las Sesiones (CSV)",
            data=df_sessions_full.to_csv(index=False).encode('utf-8'),
            file_name="all_sessions_data.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay sesiones registradas para mostrar o descargar.")