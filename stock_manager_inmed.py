import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
st.set_page_config(page_title="INMED Stock", page_icon="🧪", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"
MOT_DE_PASSE_GESTION = "INMED2026"

# Chargement données
@st.cache_data(ttl=300)
def load_data():
    return pd.read_csv(SHEET_URL)

# Initialisation état
if 'basket' not in st.session_state: st.session_state.basket = []
if 'auth_gest' not in st.session_state: st.session_state.auth_gest = False

data = load_data()
cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())

# --- UI MODERNE ---
st.title("🧪 Portail INMED")
tab1, tab2, tab3 = st.tabs(["🛒 Commander", "🛠️ Gestion", "🤖 Assistant"])

with tab1:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        cat_select = st.selectbox("Catégorie", cats)
    with col_b:
        query = st.text_input("🔍 Rechercher un produit")

    # Filtrage
    filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
    if query:
        filtered_df = filtered_df[filtered_df['Désignation'].str.contains(query, case=False, na=False)]

    # Affichage produits
    selected_idx = st.selectbox("Choisir l'article", filtered_df.index, format_func=lambda i: filtered_df.loc[i, 'Désignation'])
    item = data.loc[selected_idx]
    
    if st.button("➕ Ajouter au panier"):
        st.session_state.basket.append({'designation': item['Désignation'], 'qty': 1})
        st.rerun()

    st.write("### 🛒 Panier")
    st.write(st.session_state.basket)

with tab2:
    if not st.session_state.auth_gest:
        if st.text_input("Mot de passe", type="password") == MOT_DE_PASSE_GESTION:
            st.session_state.auth_gest = True
            st.rerun()
    else:
        st.dataframe(data)

with tab3:
    st.info("Posez vos questions sur le stock ici.")
    if prompt := st.chat_input("Question ?"):
        st.chat_message("user").write(prompt)
        st.chat_message("assistant").write("L'IA est prête (configurez votre clé Groq pour activer).")
