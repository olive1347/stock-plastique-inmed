import streamlit as st
import pandas as pd
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

@st.cache_data(ttl=60)
def load_data():
    try:
        url = st.secrets.get("SHEET_URL")
        if not url: return None
        return pd.read_csv(url)
    except: return None

# --- FONCTION VISION CORRIGÉE ---
def analyze_image_with_ai(image_data):
    # Sécurisation de la réponse API pour éviter le crash 'choices'
    try:
        # Note : Assurez-vous d'utiliser un modèle Vision compatible sur Groq
        # Si 'choices' manque, c'est que la requête est rejetée par l'API
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.2-11b-vision-preview",
                "messages": [{"role": "user", "content": "Analyse ce produit..."}],
            }, timeout=15
        )
        data = response.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        else:
            return f"Réponse API invalide : {data}"
    except Exception as e:
        return f"Erreur de vision : {str(e)}"

# --- INTERFACE ---
st.set_page_config(page_title="INMED Stock", layout="wide")
data = load_data()

if data is None:
    st.error("Données non chargées. Vérifiez SHEET_URL dans les secrets.")
else:
    tab1, tab2 = st.tabs(["🛒 Commande", "📸 Contrôle Qualité"])
    
    with tab1:
        st.write("Gestion des commandes...")
        # ... (votre code de commande ici)

    with tab2:
        st.subheader("📸 Contrôle Qualité")
        uploaded_file = st.file_uploader("Prendre une photo", type=["jpg", "png"])
        if uploaded_file and st.button("Analyser"):
            result = analyze_image_with_ai(uploaded_file)
            st.write(result)
