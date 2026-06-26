import streamlit as st
import pandas as pd
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
# Définition de la variable globale pour éviter l'erreur NameError
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"
MOT_DE_PASSE_GESTION = "INMED2026" 
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        return str(e)

# --- FONCTION D'INTERROGATION IA ---
def ask_ai(question, context):
    if not GROQ_API_KEY:
        return "⚠️ La clé API Groq n'est pas configurée dans les secrets."
    
    prompt = f"""Tu es l'assistant du laboratoire INMED. Réponds aux questions sur le stock de plastique.
    Contexte actuel du stock :
    {context}
    
    Question de l'utilisateur : {question}
    """
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5
            },
            timeout=10
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erreur de communication avec l'IA : {str(e)}"

# --- FONCTION D'ENVOI D'E-MAIL ---
def send_basket_email(nom, basket):
    destinataire = "olivier.lassalle@inserm.fr"
    sender = st.secrets.get("INSERM_EMAIL", "olivier.lassalle@inserm.fr")
    password = st.secrets.get("INSERM_PASSWORD", "")
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = destinataire
    msg['Subject'] = f"🧪 Nouvelle demande de matériel - {nom}"
    
    html_items = ""
    for item in basket:
        html_items += f"""
        <li style="margin-bottom:10px;">
            <b>{item['designation']}</b> (Réf: {item['ref_fab']})<br>
            Quantité : {item['qty']} x (Cdt: {item['cond']})<br>
            <small style="color:gray;">Info: {item['info']}</small>
        </li>
        """
    
    body = f"""
    <h2>Nouvelle demande de matériel Plastique</h2>
    <p><b>Demandeur :</b> {nom}</p>
    <ul style="list-style-type:none; padding:0;">{html_items}</ul>
    """
    msg.attach(MIMEText(body, 'html'))
    
    try:
        server = smtplib.SMTP("smtp.inserm.fr", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, destinataire, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi : {e}")
        return False

# --- INTERFACE PRINCIPALE ---
st.set_page_config(page_title="Demande plastique - INMED", page_icon="🧪", layout="wide")
st.title("🧪 Demande plastique - INMED")

if 'reload_key' not in st.session_state: st.session_state.reload_key = 0
if 'auth_gest' not in st.session_state: st.session_state.auth_gest = False
if 'basket' not in st.session_state: st.session_state.basket = []
if 'chat_hist' not in st.session_state: st.session_state.chat_hist = []

data = load_data(st.session_state.reload_key)

if isinstance(data, str):
    st.error(f"Erreur lors du chargement : {data}")
elif data.empty:
    st.warning("Le fichier est vide.")
else:
    # --- CALCUL DES CATÉGORIES ICI (Corrigé) ---
    cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())
    
    tab_cmd, tab_gest, tab_faq = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire", "❓ FAQ IA"])

    with tab_cmd:
        st.subheader("Passer une commande")
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        search_query = st.text_input("🔍 Rechercher un article :")
        
        filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
        if search_query:
            filtered_df = filtered_df[filtered_df['Désignation'].str.contains(search_query, case=False, na=False)]
        
        if not filtered_df.empty:
            selected_idx = st.selectbox(
                "3. Choisir un article :", 
                options=filtered_df.index, 
                format_func=lambda i: f"{filtered_df.loc[i, 'Désignation']} — {filtered_df.loc[i, 'Informations']}"
            )
            
            item = data.loc[selected_idx]
            qty = st.number_input("Quantité", min_value=1, value=1)
            
            if st.button("➕ Ajouter au panier"):
                st.session_state.basket.append({
                    'designation': item['Désignation'],
                    'qty': qty,
                    'cond': item.get('Conditionnement', 'N/A'),
                    'info': item.get('Informations', 'N/A'),
                    'ref_fab': item.get('Ref Fabricant', 'N/A')
                })
                st.rerun()
        
        st.divider()
        st.subheader("🛒 Mon Panier")
        if st.session_state.basket:
            for idx, item in enumerate(st.session_state.basket):
                col1, col2 = st.columns([4, 1])
                col1.write(f"{item['qty']} x **{item['designation']}** <small>({item['cond']})</small>", unsafe_allow_html=True)
                if col2.button("❌", key=f"del_{idx}"):
                    st.session_state.basket.pop(idx)
                    st.rerun()
            
            nom = st.text_input("Votre Nom")
            if st.button("🚀 Envoyer la commande"):
                if nom and send_basket_email(nom, st.session_state.basket):
                    st.success("Commande envoyée !")
                    st.session_state.basket = []
                    st.rerun()

    with tab_faq:
        # ... (Logique IA identique)
        if prompt := st.chat_input("Ex: Quel plastique pour 20-200µl ?"):
            st.session_state.chat_hist.append(("user", prompt))
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                response = ask_ai(prompt, data.to_string())
                st.write(response)
                st.session_state.chat_hist.append(("assistant", response))
