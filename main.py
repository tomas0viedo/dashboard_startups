""" import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import pandas as pd
import altair as alt

# ESTA ES LA PRIMERA LLAMADA A UNA FUNCIÓN DE STREAMLIT Y DEBE IR AQUÍ
st.set_page_config(layout="wide")

load_dotenv()

# --- Conexión a MongoDB ---
@st.cache_resource
def init_connection():
    try:
        mongo_url = os.getenv("DATABASE_URL")
        if not mongo_url:
            st.warning("DATABASE_URL no encontrada en .env, usando la URL hardcodeada.")
            # Asegúrate de que esta URL sea correcta si no usas .env
            mongo_url = "mongodb+srv://maxiesco:maxiesco@cluster0.3zdo3lp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

        client = MongoClient(mongo_url, server_api=ServerApi('1'))
        db = client["Cluster0"]
        
        client.admin.command('ping') 
        st.success("✅ Conectado a MongoDB Atlas.")
        return db
    except Exception as e:
        st.error(f"❌ Error al conectar a MongoDB Atlas: {e}")
        st.error("Por favor, verifica tu cadena de conexión (DATABASE_URL) y la configuración del acceso a la red en MongoDB Atlas.")
        return None

db = init_connection()

# Asegúrate de que startups_collection se inicializa solo si db no es None
startups_collection = db["startup"] if db is not None else None

st.title("📊 Dashboard de Startups")

if startups_collection is None:
    st.warning("No se pudo establecer conexión con la base de datos o la colección 'startup'. Por favor, verifica tu configuración y vuelve a cargar la aplicación.")
else:
    # --- Endpoints como funciones para Streamlit ---

    # Función para cargar todas las startups desde MongoDB para las sugerencias
    def load_all_startups_for_suggestions():
        return list(startups_collection.find({}))

    def get_awards_by_sector():
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
            {"$match": {"awardsInt": {"$ne": None}}},
            {"$group": {"_id": "$sector", "total_awards": {"$sum": "$awardsInt"}}},
            {"$sort": {"total_awards": -1}}
        ]
        result = list(startups_collection.aggregate(pipeline))
        data = [{"sector": doc["_id"] or "Otros", "total_awards": doc["total_awards"]} for doc in result]
        return pd.DataFrame(data)

    def get_contact_web_status():
        with_contact = startups_collection.count_documents({"contactPerson": {"$exists": True, "$ne": None, "$ne": ""}})
        without_contact = startups_collection.count_documents({"$or": [{"contactPerson": {"$exists": False}}, {"contactPerson": None}, {"contactPerson": ""}]})
        with_website = startups_collection.count_documents({"website": {"$exists": True, "$ne": None, "$ne": ""}})
        without_website = startups_collection.count_documents({"$or": [{"website": {"$exists": False}}, {"website": None}, {"website": ""}]})

        return pd.DataFrame([
            {"status": "Con contacto", "count": with_contact},
            {"status": "Sin contacto", "count": without_contact},
            {"status": "Con web", "count": with_website},
            {"status": "Sin web", "count": without_website}
        ])

    def get_sector_distribution():
        pipeline = [
            {"$group": {
                "_id": "$sector",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        result = list(startups_collection.aggregate(pipeline))
        data = [{"sector": doc["_id"] or "Otros", "count": doc["count"]} for doc in result]
        return pd.DataFrame(data)

    def get_top_awards():
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
        return pd.DataFrame(result)

    def get_contacts_list():
        cursor = startups_collection.find(
            {"contactPerson": {"$ne": None, "$ne": ""}},
            {"company": 1, "contactPerson": 1, "email": 1, "sector": 1, "_id": 0}
        )
        data = list(cursor)
        return pd.DataFrame(data)

    # --- Diseño del Dashboard de Estadísticas Clave ---
    st.header("Estadísticas Clave")
    
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Premios por Sector")
        awards_data = get_awards_by_sector()
        if not awards_data.empty:
            st.bar_chart(awards_data.set_index("sector"))
        else:
            st.info("No hay datos de premios por sector para mostrar.")

    with col2:
        st.subheader("Distribución de Sectores")
        sector_data = get_sector_distribution()
        if not sector_data.empty:
            chart = alt.Chart(sector_data).mark_arc().encode(
                theta=alt.Theta(field="count", type="quantitative"),
                color=alt.Color(field="sector", type="nominal", title="Sector"),
                order=alt.Order(field="count", sort="descending"),
                tooltip=["sector", "count"]
            ).properties(
                title="Distribución de Startups por Sector"
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No hay datos de distribución de sectores para mostrar.")

    
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Estado de Contacto y Web")
        contact_web_data = get_contact_web_status()
        if not contact_web_data.empty:
            st.bar_chart(contact_web_data.set_index("status"))
        else:
            st.info("No hay datos de estado de contacto y web para mostrar.")

    with col4:
        st.subheader("Top 5 Startups con Más Premios")
        top_awards_data = get_top_awards()
        if not top_awards_data.empty:
            st.table(top_awards_data)
        else:
            st.info("No hay datos de las startups con más premios para mostrar.")
    
    st.header("Listado de Contactos")
    contacts_data = get_contacts_list()
    if not contacts_data.empty:
        st.dataframe(contacts_data)
    else:
        st.info("No hay contactos para mostrar.")

    # --- NUEVA SECCIÓN: Conexiones Sugeridas ---
    st.markdown("---") # Separador visual
    st.header("🤝 Conexiones Sugeridas para Startups")

    all_startups_for_suggestions = load_all_startups_for_suggestions()

    if not all_startups_for_suggestions:
        st.warning("No se encontraron startups para sugerencias. Asegúrate de que la colección 'startup' tiene documentos.")
    else:
        startup_names_map = {s.get('company', 'Sin Nombre'): s for s in all_startups_for_suggestions if 'company' in s}
        valid_startup_names = [name for name in startup_names_map.keys() if name != 'Sin Nombre']

        if valid_startup_names:
            selected_company_name = st.selectbox(
                "Selecciona tu Startup para encontrar conexiones:",
                options=valid_startup_names,
                key="suggestion_selectbox"
            )

            if selected_company_name:
                selected_startup = startup_names_map[selected_company_name]
                
                st.write(f"---")
                st.subheader(f"Sugerencias para **{selected_startup.get('company', 'Tu Startup')}**")

                target_sector = selected_startup.get('sector')
                target_stage = selected_startup.get('stage')

                suggested_startups = []
                for s in all_startups_for_suggestions:
                    if s.get('_id') == selected_startup.get('_id'):
                        continue 

                    if (target_sector and s.get('sector') == target_sector) or \
                       (target_stage and s.get('stage') == target_stage):
                        suggested_startups.append(s)
                
                # --- CAMBIO INTEGRADO AQUÍ: Limitar a los primeros 5 ---
                top_5_suggested = suggested_startups[:5] # Toma solo los primeros 5 elementos

                if top_5_suggested: 
                    st.write("Conecta con startups que comparten tu sector o etapa (Top 5):") 
                    for s in top_5_suggested: # Itera sobre la lista limitada
                        with st.expander(f"**{s.get('company', 'Startup Desconocida')}**"):
                            st.write(f"**Sector:** {s.get('sector', 'N/A')}")
                            st.write(f"**Etapa:** {s.get('stage', 'N/A')}")
                            st.write(f"**Descripción:** {s.get('description', 'N/A')}")
                            if s.get('website'):
                                st.markdown(f"**Web:** [{s['website']}]({s['website']})")
                            if s.get('email'):
                                st.write(f"**Contacto:** {s.get('email', 'N/A')}")
                else:
                    st.info("No se encontraron sugerencias de conexión para esta startup en base a sector o etapa.")
        else:
            st.info("No hay nombres de startups válidos para mostrar sugerencias.")

""" 

import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import pandas as pd
import altair as alt # Aunque no se usa directamente, se mantiene si piensas usarlo para otros gráficos
import plotly.express as px # Importado para gráficos más "pro" como los que ya usas
from datetime import datetime
from bson.objectid import ObjectId

# Configuración de la página (DEBE SER LO PRIMERO EN EL SCRIPT)
st.set_page_config(layout="wide", page_title="Dashboard de Startups y Sesiones")

# Intenta forzar el fondo blanco. Streamlit tiene un control más fuerte sobre esto con los temas.
# Para un control total, considera configurar el tema 'light' en .streamlit/config.toml
st.markdown(
    """
    <style>
    .stApp {
        background-color: white;
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
        st.success("✅ Conectado a MongoDB Atlas para el Dashboard.")
        return client["Cluster0"]
    except Exception as e:
        st.error(f"❌ Error al conectar a MongoDB Atlas: {e}")
        st.error("Por favor, verifica tu cadena de conexión (DATABASE_URL) y la configuración del acceso a la red en MongoDB Atlas.")
        return None

db = init_connection()

# --- Obtener Colecciones ---
# CORRECCIÓN: Usar 'is not None' para verificar la conexión 'db'
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

# CORRECCIÓN: Eliminar @st.cache_data de get_data (si lo tenías en tu versión real)
def get_data(collection):
    if collection is None:
        return []
    data = list(collection.find({}))
    return [serialize_doc(doc) for doc in data]

@st.cache_data(ttl=300)
def get_sessions_with_details():
    if sessions_collection is None or mentors_collection is None or startups_collection is None:
        # No mostrar error aquí, ya se maneja al inicio si la conexión falla
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
            "mentor_id": "$mentor_info._id", # Para filtrar por mentor_id
            "mentor_name": "$mentor_info.name",
            "startup_id": "$startup_info._id", # Para filtrar por startup_id
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
    sessions_detailed = get_sessions_with_details() # Usamos la función que devuelve detalles

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
    if sessions_detailed: # Usamos sessions_detailed aquí
        df_sessions = pd.DataFrame(sessions_detailed)
        status_counts = df_sessions['status'].value_counts().reset_index()
        status_counts.columns = ['Estado', 'Count']
        fig_status = px.bar(status_counts, x='Estado', y='Count', title='Conteo de Sesiones por Estado',
                            color='Estado', text='Count')
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
            col_order_detail = ["date", "mentor_name", "startup_company", "topic", "status", "summary", "comments"]
            df_display_detail = df_filtered_sessions.reindex(columns=[col for col in col_order_detail if col in df_filtered_sessions.columns])
            st.dataframe(df_display_detail, use_container_width=True)
        else:
            st.info("No hay sesiones con este estado para mostrar.")
    else:
        st.info("No hay datos de sesiones para el gráfico de estado.")

    st.markdown("---")

    # --- NUEVA SECCIÓN: Sesiones Firmadas por Mentor ---
    st.header("🚀 Sesiones Firmadas por Mentor (Vista Profesional)")
    if mentors and sessions_detailed:
        # Obtener una lista de nombres de mentores únicos que tienen sesiones firmadas
        mentors_with_signed_sessions = sorted(list(set([
            s.get('mentor_name') for s in sessions_detailed 
            if s.get('status') == 'signed' and s.get('mentor_name')
        ])))

        if mentors_with_signed_sessions:
            selected_mentor_name = st.selectbox(
                "Selecciona un Mentor para ver sus sesiones firmadas:",
                options=['Selecciona un mentor'] + mentors_with_signed_sessions,
                key='mentor_signed_sessions_select'
            )

            if selected_mentor_name != 'Selecciona un mentor':
                st.subheader(f"Sesiones Firmadas por {selected_mentor_name}")
                
                filtered_mentor_sessions = [
                    s for s in sessions_detailed 
                    if s.get('mentor_name') == selected_mentor_name and s.get('status') == 'signed'
                ]
                
                if filtered_mentor_sessions:
                    df_mentor_sessions = pd.DataFrame(filtered_mentor_sessions)
                    # Columnas relevantes para mostrar
                    display_cols = ['date', 'startup_company', 'topic', 'duration', 'summary', 'comments']
                    st.dataframe(df_mentor_sessions[display_cols], use_container_width=True)
                else:
                    st.info(f"No hay sesiones firmadas para {selected_mentor_name}.")
            else:
                st.info("Por favor, selecciona un mentor para ver sus sesiones firmadas.")
        else:
            st.info("No hay mentores con sesiones firmadas para mostrar.")
    else:
        st.info("No hay datos de mentores o sesiones para mostrar esta sección.")

    st.markdown("---")

    # --- Listado de Contactos ---
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
    
    if sessions_detailed: # Usamos sessions_detailed aquí
        df_sessions_full = pd.DataFrame(sessions_detailed)
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