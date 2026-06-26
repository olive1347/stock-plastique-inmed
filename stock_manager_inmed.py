import streamlit as st
import pandas as pd
import time

# CONFIGURATION
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"

@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        return str(e)

st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
st.title("🧪 GestStock INMED")

if 'reload_key' not in st.session_state:
    st.session_state.reload_key = 0

data = load_data(st.session_state.reload_key)

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
            
            # Menu déroulant enrichi pour le choix
            def format_func(idx):
                item = filtered_df.loc[idx]
                cond = item.get('Conditionnement', '')
                ref = item.get('Ref fabricant', '')
                return f"{item['Désignation']} — [{cond}] (Réf: {ref})"

            selected_idx = st.selectbox(
                "2. Choisir un article :", 
                options=filtered_df.index, 
                format_func=format_func
            )
            
            if selected_idx is not None:
                item = filtered_df.loc[selected_idx]
                
                # Affichage épuré : uniquement la colonne Informations
                st.info(f"**Informations sur l'article :**\n\n{item.get('Informations', 'Aucune information disponible.')}")
                
                qty = st.number_input("Quantité", min_value=1, value=1)
                nom = st.text_input("Votre Nom")
                if st.button("🚀 Envoyer la commande"):
                    if nom:
                        st.success(f"Commande de {qty} x {item['Désignation']} envoyée par {nom} !")
                    else:
                        st.warning("Veuillez renseigner votre nom.")
        else:
            st.error("Colonnes manquantes dans votre fichier. Vérifiez les en-têtes : 'Catégorie', 'Désignation', etc.")

    with tab_gest:
        st.subheader("🛠️ Édition du Stock")
        st.dataframe(data, use_container_width=True)
        if st.button("🔄 Rafraîchir les données"):
            st.session_state.reload_key += 1
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Note : Les modifications doivent être faites dans le Google Sheet source.")
