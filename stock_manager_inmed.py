import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

# --- CONFIGURATION ---
MOT_DE_PASSE_GESTION = "INMED2026" 
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        url = st.secrets.get("SHEET_URL")
        if not url: return "URL non configurée dans les secrets."
        df = pd.read_csv(url)
        # Nettoyage automatique des noms de colonnes pour éviter les espaces invisibles
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return str(e)

def ask_ai(question, context):
    if not GROQ_API_KEY: return "⚠️ Clé API Groq manquante."
    prompt = f"Tu es l'assistant INMED. Contexte stock : {context}. Question : {question}"
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]},
            timeout=10
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e: return f"Erreur IA : {str(e)}"

def send_basket_email(nom, basket):
    destinataire = "olivier.lassalle@inserm.fr"
    sender = st.secrets.get("INSERM_EMAIL", "olivier.lassalle@inserm.fr")
    password = st.secrets.get("INSERM_PASSWORD", "")
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = destinataire
    msg['Subject'] = f"🧪 Nouvelle demande de matériel - {nom}"
    
    html_items = "".join([f"<li><b>{i['designation']}</b> (Réf: {i['ref_fab']}) - Qté: {i['qty']} (Cdt: {i['cond']})</li>" for i in basket])
    body = f"<h2>Nouvelle demande de matériel</h2><p><b>Demandeur :</b> {nom}</p><ul>{html_items}</ul>"
    msg.attach(MIMEText(body, 'html'))
    
    try:
        server = smtplib.SMTP("smtp.inserm.fr", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, destinataire, msg.as_string())
        server.quit()
        return True
    except: return False

# --- INTERFACE ---
st.set_page_config(page_title="Demande plastique - INMED", page_icon="🧪", layout="wide")
st.title("🧪 Demande plastique - INMED")

if 'reload_key' not in st.session_state: st.session_state.reload_key = 0
if 'auth_gest' not in st.session_state: st.session_state.auth_gest = False
if 'basket' not in st.session_state: st.session_state.basket = []

data = load_data(st.session_state.reload_key)

if isinstance(data, str):
    st.error(f"Erreur chargement : {data}")
else:
    # S'assurer que les colonnes nécessaires existent
    required_cols = ['Catégorie', 'Désignation']
    if not all(col in data.columns for col in required_cols):
        st.error(f"Erreur : Le fichier CSV doit contenir les colonnes : {', '.join(required_cols)}")
        st.stop()

    cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())
    tab_cmd, tab_gest, tab_faq = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire", "❓ FAQ IA"])

    with tab_cmd:
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
        selected_idx = st.selectbox("3. Choisir un article :", options=filtered_df.index, format_func=lambda i: filtered_df.loc[i, 'Désignation'])
        item = data.loc[selected_idx]
        
        # Correction affichage Informations
        info_texte = item.get('Informations') if 'Informations' in item else ""
        if pd.isna(info_texte): info_texte = "Aucune information complémentaire."
        
        cdt_texte = item.get('Conditionnement', 'N/A')
        ref_texte = item.get('Ref Fabricant', 'N/A')
        
        st.info(f"**Info :** {info_texte} \n *Cdt : {cdt_texte}* | *Réf : {ref_texte}*")
        
        qty = st.number_input("Quantité", min_value=1, value=1)
        if st.button("➕ Ajouter au panier"):
            st.session_state.basket.append({'designation': item['Désignation'], 'qty': qty, 'cond': cdt_texte, 'ref_fab': ref_texte})
            st.rerun()
        
        if st.session_state.basket:
            st.subheader("🛒 Mon Panier")
            for idx, i in enumerate(st.session_state.basket):
                if st.button(f"❌ {i['qty']} x {i['designation']}", key=f"del_{idx}"):
                    st.session_state.basket.pop(idx); st.rerun()
            nom = st.text_input("Votre Nom")
            if st.button("🚀 Envoyer la commande"):
                if nom and send_basket_email(nom, st.session_state.basket):
                    st.success("✅ Commande envoyée !"); st.session_state.basket = []
                else: st.warning("Nom requis.")

    with tab_gest:
        if not st.session_state.auth_gest:
            if st.text_input("🔑 Mot de passe :", type="password") == MOT_DE_PASSE_GESTION:
                st.session_state.auth_gest = True; st.rerun()
        else:
            st.dataframe(data, use_container_width=True)

    with tab_faq:
        if prompt := st.chat_input("Question ?"):
            st.write(ask_ai(prompt, data.to_string()))
