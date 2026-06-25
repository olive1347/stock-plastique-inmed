import streamlit as st
import pandas as pd

# CONFIGURATION
# Remplacez ce lien par le lien CSV généré par "Publier sur le web" de votre Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"

# Fonction pour charger les données avec mise en cache
@st.cache_data(ttl=60)
def load_data():
    try:
        return pd.read_csv(SHEET_URL)
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        return pd.DataFrame()

# Configuration de la page
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
st.title("🧪 GestStock INMED")

df = load_data()

# Création des onglets
tab_cmd, tab_gest = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire"])

with tab_cmd:
    st.subheader("Passer une commande")
    if not df.empty:
        # Filtre par catégorie
        cats = ["Toutes"] + df['Catégorie'].dropna().unique().tolist()
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        
        filtered_df = df if cat_select == "Toutes" else df[df['Catégorie'] == cat_select]
        
        # Sélection de l'article
        selected_idx = st.selectbox(
            "2. Choisir un article :", 
            options=filtered_df.index, 
            format_func=lambda x: f"{filtered_df.loc[x, 'Désignation']} ({filtered_df.loc[x, 'Informations']})"
        )
        
        if selected_idx is not None:
            item = filtered_df.loc[selected_idx]
            st.info(f"**Article :** {item['Désignation']} | **Cond :** {item['Conditionnement']}")
            
            qty = st.number_input("Quantité", min_value=1, value=1)
            nom = st.text_input("Votre Nom")
            
            if st.button("🚀 Envoyer la commande"):
                if nom:
                    st.success(f"Commande de {qty} x {item['Désignation']} envoyée par {nom} !")
                else:
                    st.warning("Veuillez renseigner votre nom.")
    else:
        st.warning("Données non chargées. Vérifiez le lien du Google Sheet.")

with tab_gest:
    st.subheader("🛠️ Édition du Stock")
    st.write("Pour modifier les stocks, modifiez directement votre fichier Google Sheet original.")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    
    if st.button("🔄 Rafraîchir les données"):
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Note : Les modifications doivent être faites dans le Google Sheet source.")
