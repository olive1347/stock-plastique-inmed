import streamlit as st
import pandas as pd
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
st.set_page_config(page_title="INMED Lab Stock", page_icon="🧪", layout="wide")

# CSS personnalisé pour un look plus moderne
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .css-1r6slbo { padding-top: 1rem; }
    .stButton>button { border-radius: 20px; border: none; background-color: #007bff; color: white; transition: 0.3s; }
    .stButton>button:hover { background-color: #0056b3; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# (Gardez vos fonctions load_data, ask_ai, send_basket_email telles quelles)

# --- INTERFACE ---
st.title("🧪 Portail de Gestion INMED")
st.markdown("---")

# Navigation latérale pour épurer l'interface principale
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/fr/b/bd/Inserm_logo.svg", width=150)
    st.title("Menu")
    page = st.radio("Navigation", ["🛒 Commander", "🛠️ Inventaire", "🤖 FAQ IA"])
    st.markdown("---")
    st.info("Besoin d'aide ? Contactez l'administration.")

if page == "🛒 Commander":
    st.header("🛒 Commander du matériel")
    # Utilisation de colonnes pour un rendu plus aéré
    col1, col2 = st.columns([1, 2])
    with col1:
        cat_select = st.selectbox("Catégorie", cats)
    with col2:
        search_query = st.text_input("🔍 Rechercher un article", placeholder="Tapez le nom du plastique...")

    # ... (Logique de filtrage et panier)
    st.success(f"Panier actuel : {len(st.session_state.basket)} article(s)")

elif page == "🛠️ Inventaire":
    st.header("🛠️ Gestion Inventaire")
    if not st.session_state.auth_gest:
        with st.form("login"):
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion"):
                if pw == MOT_DE_PASSE_GESTION:
                    st.session_state.auth_gest = True
                    st.rerun()
    else:
        st.dataframe(data, use_container_width=True, hide_index=True)

elif page == "🤖 FAQ IA":
    st.header("🤖 Assistant IA INMED")
    st.chat_message("assistant").write("Bonjour ! Posez-moi vos questions sur le stock.")
    if prompt := st.chat_input("Ex: quel est le stock de cônes 10µl ?"):
        with st.chat_message("user"): st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                response = ask_ai(prompt, data.to_string())
                st.write(response)
