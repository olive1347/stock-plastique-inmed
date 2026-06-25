import streamlit as st
import pandas as pd

# CONFIGURATION
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        return str(e)

st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
st.title("🧪 GestStock INMED")

data = load_data()

if isinstance(data, str):
    st.error(f"Erreur lors du chargement des données : {data}")
    st.write("Vérifiez que votre fichier Google Sheet contient bien une première ligne avec des titres de colonnes.")
elif data.empty:
    st.warning("Le fichier est vide.")
else:
    # DEBUG : Affiche les colonnes trouvées pour vérifier la correspondance
    st.sidebar.write("Colonnes détectées :", data.columns.tolist())
    
    tab_cmd, tab_gest = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire"])

    with tab_cmd:
        st.subheader("Passer une commande")
        # Vérification des colonnes nécessaires pour le filtre
        if 'Catégorie' in data.columns and 'Désignation' in data.columns:
            cats = ["Toutes"] + data['Catégorie'].dropna().unique().tolist()
            cat_select = st.selectbox("1. Choisir une catégorie :", cats)
            
            filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
            
            # Sélection de l'article
            selected_idx = st.selectbox(
                "2. Choisir un article :", 
                options=filtered_df.index, 
                format_func=lambda x: f"{filtered_df.loc[x, 'Désignation']}"
            )
            
            if selected_idx is not None:
                item = filtered_df.loc[selected_idx]
                st.info(f"**Article :** {item['Désignation']}")
                qty = st.number_input("Quantité", min_value=1, value=1)
                nom = st.text_input("Votre Nom")
                if st.button("🚀 Envoyer la commande"):
                    st.success(f"Commande de {qty} x {item['Désignation']} envoyée par {nom} !")
        else:
            st.error("Les colonnes 'Catégorie' ou 'Désignation' sont introuvables. Vérifiez les titres dans votre Google Sheet.")

    with tab_gest:
        st.subheader("🛠️ Édition du Stock")
        st.dataframe(data, use_container_width=True)
        if st.button("🔄 Rafraîchir"):
            st.rerun()
