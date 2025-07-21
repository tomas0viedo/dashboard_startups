import streamlit as st
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