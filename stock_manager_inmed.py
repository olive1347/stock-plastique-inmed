import streamlit as st
import pandas as pd
import smtplib
import requests
import base64 # 👁️ NOUVEAU
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
# --- FONCTION D'ANALYSE D'IMAGE (Vision) --- # 👁️ NOUVEAU
def analyze_image_with_ai(image_bytes):
    """
    Envoie l'image à un modèle Vision (ex: Gemini).
    Note : Vous devez adapter l'URL/API selon votre fournisseur Vision.
    """
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Exemple de structure pour un modèle Vision
    prompt = "Analyse cette photo de matériel de laboratoire. Est-ce conforme ? Y a-t-il des dommages ou une péremption visible ? Réponds très brièvement."
    
    # --- LOGIQUE D'APPEL API VISION ICI ---
    # return "Simulé : L'IA a détecté que le plastique est intact."
    return "👁️ Module Vision prêt : Veuillez connecter une API Vision (ex: Google Gemini) pour finaliser l'analyse."

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
        return "⚠️ La clé API Groq n'est pas configurée."
    
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
        return f"Erreur IA : {str(e)}"

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
# Modification des onglets pour ajouter QC
cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())
tab_cmd, tab_gest, tab_faq, tab_qc = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire", "❓ FAQ IA", "👁️ Contrôle Qualité"]) # 👁️ NOUVEAU

if 'basket' not in st.session_state: st.session_state.basket = []

data = load_data(st.session_state.reload_key)

if isinstance(data, str):
    st.error(f"Erreur chargement : {data}")
elif data.empty:
    st.warning("Le fichier est vide.")
else:
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
            
            # Réaffichage de la fenêtre bleue détaillée
            st.info(f"**Informations sur l'article :**\n\n{item.get('Informations', 'Aucune info')}\n\n*Conditionnement : {item.get('Conditionnement', 'N/A')}*\n*Réf Fabricant : {item.get('Ref Fabricant', 'N/A')}*")
            
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
                    st.success("✅ Commande envoyée avec succès !")
                    st.session_state.basket = []
                    st.balloons()
                elif not nom:
                    st.warning("Veuillez renseigner votre nom.")

    with tab_gest:
        st.subheader("🛠️ Gestion Inventaire")
        if not st.session_state.auth_gest:
            password = st.text_input("🔑 Mot de passe :", type="password")
            if st.button("Valider"):
                if password == MOT_DE_PASSE_GESTION:
                    st.session_state.auth_gest = True
                    st.rerun()
        else:
            if st.button("🔒 Se déconnecter"):
                st.session_state.auth_gest = False
                st.rerun()
            st.dataframe(data, use_container_width=True)
            if st.button("🔄 Rafraîchir les données"):
                st.session_state.reload_key += 1
                st.rerun()

    with tab_faq:
        if prompt := st.chat_input("Ex: Quel plastique pour 20-200µl ?"):
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                response = ask_ai(prompt, data.to_string())
                st.write(response)

    with tab_qc: # 👁️ NOUVEAU
        st.subheader("👁️ Contrôle Qualité par Vision")
        st.write("Prenez une photo du matériel pour vérifier son état (détérioration, conformité).")
        
        uploaded_file = st.camera_input("Prendre une photo")
        
        if uploaded_file:
            st.image(uploaded_file, caption="Image capturée", use_container_width=True)
            if st.button("🚀 Analyser avec l'IA"):
                with st.spinner("Analyse en cours..."):
                    resultat = analyze_image_with_ai(uploaded_file.getvalue())
                    st.success(f"Résultat : {resultat}")
