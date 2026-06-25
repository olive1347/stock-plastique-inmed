import streamlit as st
import pandas as pd
import time

# CONFIGURATION
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"

# On utilise un paramètre 'force_reload' pour forcer la mise à jour
@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        return str(e)

# Configuration de la page
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
st.title("🧪 GestStock INMED")

# Initialisation du déclencheur de rechargement dans la session
if 'reload_key' not in st.session_state:
    st.session_state.reload_key = 0

# Chargement des données avec la clé qui change au clic
data = load_data(st.session_state.reload_key)

# Vérification des erreurs
if isinstance(data, str):
    st.error(f"Erreur lors du chargement : {data}")
elif data.empty:
    st.warning("Le fichier est vide.")
else:
    tab_cmd, tab_gest = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire"])

    with tab_cmd:
        st.subheader("Passer une commande")
        if 'Catégorie' in data.columns and 'Désignation' in data.columns:
            cats = ["Toutes"] + data['Catégorie'].dropna().unique().tolist()
            cat_select = st.selectbox("1. Choisir une catégorie :", cats)
            
            filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
            
            selected_idx = st.selectbox(
                "2. Choisir un article :", 
                options=filtered_df.index, 
                format_func=lambda x: f"{filtered_df.loc[x, 'Désignation']}"
            )
            
            if selected_idx is not None:
                item = filtered_df.loc[selected_idx]
                st.info(f"""
                **Article :** {item.get('Désignation', 'N/A')}  
                **Conditionnement :** {item.get('Conditionnement', 'N/A')}  
                **Informations :** {item.get('Informations', 'N/A')}
                """)
                
                qty = st.number_input("Quantité", min_value=1, value=1)
                nom = st.text_input("Votre Nom")
                if st.button("🚀 Envoyer la commande"):
                    if nom:
                        st.success(f"Commande de {qty} x {item['Désignation']} envoyée par {nom} !")
                    else:
                        st.warning("Veuillez renseigner votre nom.")

    with tab_gest:
        st.subheader("🛠️ Édition du Stock")
        st.dataframe(data, use_container_width=True)
        
        # Le bouton incrémente la clé, ce qui force load_data à s'exécuter à nouveau
        if st.button("🔄 Rafraîchir les données"):
            st.session_state.reload_key += 1
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Note : Les modifications doivent être faites dans le Google Sheet source.")
