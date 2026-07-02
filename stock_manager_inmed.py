import streamlit as st
import pandas as pd
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Demandes Plastique — INMED",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ajout d'une feuille de style CSS injectée pour embellir l'application
st.markdown("""
<style>
    /* Style général */
    .stApp {
        background-color: #fafbfc;
    }
    
    /* Titre de l'application */
    .main-title {
        color: #1e293b;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Cartes de panier personnalisées */
    .cart-item {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .cart-item-title {
        font-weight: 600;
        color: #0f172a;
        font-size: 1rem;
    }
    
    .cart-item-meta {
        color: #64748b;
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }
    
    .cart-item-qty {
        background: #eff6ff;
        color: #1d4ed8;
        font-weight: bold;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# --- VARIABLES ET SECRETS ---
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

# Initialisation de l'état de la session
if 'reload_key' not in st.session_state: st.session_state.reload_key = 0
if 'auth_gest' not in st.session_state: st.session_state.auth_gest = False
if 'basket' not in st.session_state: st.session_state.basket = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

data = load_data(st.session_state.reload_key)

def ask_ai(question, context):
    if not GROQ_API_KEY:
        return "⚠️ La clé API Groq n'est pas configurée dans les secrets Streamlit Cloud."
    
    prompt = f"""Tu es l'assistant IA officiel du laboratoire INMED. Réponds de façon précise, cordiale et synthétique en français.
    Voici le catalogue actuel de notre stock de plastique de laboratoire :
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
                "temperature": 0.4
            },
            timeout=10
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erreur de communication avec l'assistant IA : {str(e)}"

def send_basket_email(nom, basket):
    destinataire = "olivier.lassalle@inserm.fr"
    sender = st.secrets.get("INSERM_EMAIL", "olivier.lassalle@inserm.fr")
    password = st.secrets.get("INSERM_PASSWORD", "")
    
    if not password:
        st.error("❌ Mot de passe de messagerie (INSERM_PASSWORD) manquant dans vos secrets de configuration.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = destinataire
    msg['Subject'] = f"🧪 Nouvelle demande de matériel Plastique — {nom}"
    
    html_items = ""
    for item in basket:
        html_items += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 12px; font-weight: bold; color: #1e293b;">{item['designation']}</td>
            <td style="padding: 12px; text-align: center;"><span style="background: #eff6ff; color: #1d4ed8; padding: 4px 10px; border-radius: 9999px; font-weight: bold;">{item['qty']}</span></td>
            <td style="padding: 12px; color: #64748b;">{item['cond']}</td>
            <td style="padding: 12px; color: #64748b;">{item['ref_fab']}</td>
            <td style="padding: 12px; color: #94a3b8; font-size: 12px;">{item['info']}</td>
        </tr>
        """
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
        <div style="background-color: #1e3a8a; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; color: white;">
            <h2 style="margin: 0; font-size: 22px;">🧪 Demande de Plastique</h2>
            <p style="margin: 5px 0 0; opacity: 0.85;">Institut de Neurobiologie de la Méditerranée</p>
        </div>
        <div style="padding: 20px;">
            <p>Bonjour,</p>
            <p>Une nouvelle demande de matériel de laboratoire a été déposée par <strong>{nom}</strong>.</p>
            
            <h3 style="color: #1e3a8a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 24px;">Liste des articles demandés :</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                    <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                        <th style="padding: 12px; text-align: left; color: #475569;">Article</th>
                        <th style="padding: 12px; text-align: center; color: #475569;">Qté</th>
                        <th style="padding: 12px; text-align: left; color: #475569;">Cond.</th>
                        <th style="padding: 12px; text-align: left; color: #475569;">Réf Fab.</th>
                        <th style="padding: 12px; text-align: left; color: #475569;">Remarques</th>
                    </tr>
                </thead>
                <tbody>
                    {html_items}
                </tbody>
            </table>
            
            <p style="margin-top: 30px; font-size: 11px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                Ce mail automatique a été généré par l'application Portail Plastique INMED.
            </p>
        </div>
    </body>
    </html>
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
        st.error(f"Erreur d'envoi SMTP : {e}")
        return False

# --- RENDU DE L'INTERFACE UTILISATEUR ---
if isinstance(data, str):
    st.error(f"❌ Impossible d'accéder aux données : {data}")
elif data.empty:
    st.warning("⚠️ L'inventaire importé est vide.")
else:
    # En-tête principal moderne
    st.markdown('<div class="main-title">🧪 Portail Plastique INMED</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Commandes internes, gestion de l\'inventaire et assistant logistique</div>', unsafe_allow_html=True)

    # Déclaration des onglets
    tab_cmd, tab_gest, tab_faq = st.tabs(["🛒 Commander", "🛠️ Gestion de l'Inventaire", "🤖 Assistant IA (FAQ)"])

    with tab_cmd:
        col_select, col_search = st.columns([1, 2])
        cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())
        
        with col_select:
            cat_select = st.selectbox("📁 Filtrer par catégorie :", cats)
        with col_search:
            search_query = st.text_input("🔍 Rechercher un article par mot-clé :", placeholder="Ex : Flasque, Embout, Tube...")

        # Application des filtres
        filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
        if search_query:
            filtered_df = filtered_df[filtered_df['Désignation'].str.contains(search_query, case=False, na=False)]

        if not filtered_df.empty:
            # Formulaire de choix et d'ajout
            st.markdown("### 1. Sélectionner l'article et la quantité")
            
            selected_idx = st.selectbox(
                "Choisir le produit précis dans la liste :", 
                options=filtered_df.index, 
                format_func=lambda i: f"{filtered_df.loc[i, 'Désignation']} — Réf: {filtered_df.loc[i].get('Ref Fabricant', 'N/A')}"
            )
            
            selected_item = data.loc[selected_idx]
            
            # Présentation propre des détails du produit sélectionné
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.info(f"📦 **Conditionnement :** {selected_item.get('Conditionnement', 'Non spécifié')}")
            with detail_col2:
                st.warning(f"ℹ️ **Informations :** {selected_item.get('Informations', 'Aucune remarque')}")

            qty = st.number_input("Quantité souhaitée :", min_value=1, value=1, step=1)
            
            if st.button("➕ Ajouter l'article au panier", use_container_width=True):
                st.session_state.basket.append({
                    'designation': selected_item['Désignation'],
                    'qty': qty,
                    'cond': selected_item.get('Conditionnement', 'N/A'),
                    'info': selected_item.get('Informations', 'N/A'),
                    'ref_fab': selected_item.get('Ref Fabricant', 'N/A')
                })
                st.toast(f"✅ Ajouté : {selected_item['Désignation']} (x{qty})", icon="🛒")
                st.rerun()
        else:
            st.error("Aucun article ne correspond à vos critères de recherche.")

        st.markdown("---")
        
        # ZONE DU PANIER (Remplaçant l'ancien st.write technique)
        st.markdown("### 🛒 Votre panier actuel")
        
        if st.session_state.basket:
            # Rendu élégant de chaque élément sous forme de cartes d'action
            for idx, item in enumerate(st.session_state.basket):
                col_item_desc, col_item_action = st.columns([6, 1])
                
                with col_item_desc:
                    # Affichage HTML propre de l'article pour remplacer l'arbre JSON
                    html_card = f"""
                    <div class="cart-item">
                        <div>
                            <div class="cart-item-title">{item['designation']}</div>
                            <div class="cart-item-meta">
                                🏷️ Réf : {item['ref_fab']} &nbsp;|&nbsp; 📦 Cond : {item['cond']} &nbsp;|&nbsp; 📝 Note : {item['info']}
                            </div>
                        </div>
                        <div class="cart-item-qty">Qté : {item['qty']}</div>
                    </div>
                    """
                    st.markdown(html_card, unsafe_allow_html=True)
                
                with col_item_action:
                    # Alignement du bouton de suppression à côté du bloc
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    if st.button("❌ Supprimer", key=f"del_{idx}", use_container_width=True):
                        st.session_state.basket.pop(idx)
                        st.toast("Article retiré du panier", icon="🗑️")
                        st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Formulaire de confirmation finale
            with st.container():
                st.markdown("#### 🚀 Finaliser la demande")
                nom_demandeur = st.text_input("Saisissez votre Nom et Prénom :", placeholder="Ex : Marie Durant")
                
                if st.button("📧 Envoyer la demande par e-mail", type="primary", use_container_width=True):
                    if nom_demandeur.strip():
                        with st.spinner("Envoi en cours à l'adresse du gestionnaire..."):
                            if send_basket_email(nom_demandeur.strip(), st.session_state.basket):
                                st.success(f"🎉 Demande envoyée avec succès, {nom_demandeur} !")
                                st.balloons()
                                st.session_state.basket = []
                                st.rerun()
                    else:
                        st.error("⚠️ Veuillez renseigner votre nom avant de valider l'envoi.")
        else:
            st.info("Votre panier est actuellement vide. Sélectionnez un produit ci-dessus pour commencer.")

    with tab_gest:
        st.subheader("🛠️ Espace d'administration du stock")
        
        if not st.session_state.auth_gest:
            with st.form("auth_form"):
                passwd = st.text_input("Saisissez le code d'accès administrateur :", type="password")
                if st.form_submit_button("Se connecter"):
                    if passwd == MOT_DE_PASSE_GESTION:
                        st.session_state.auth_gest = True
                        st.success("Connexion réussie !")
                        st.rerun()
                    else:
                        st.error("Mot de passe incorrect.")
        else:
            col_admin_title, col_admin_logout = st.columns([5, 1])
            with col_admin_title:
                st.markdown("✅ **Session Administrateur active**")
            with col_admin_logout:
                if st.button("🔒 Déconnexion", use_container_width=True):
                    st.session_state.auth_gest = False
                    st.rerun()

            st.dataframe(data, use_container_width=True, hide_index=True)
            
            if st.button("🔄 Actualiser les données du tableur Google", use_container_width=True):
                st.session_state.reload_key += 1
                st.cache_data.clear()
                st.success("Les données ont été synchronisées avec succès !")
                st.rerun()

    with tab_faq:
        st.subheader("🤖 Assistant virtuel du stock")
        st.write("Interrogez l'intelligence artificielle pour connaître l'emplacement d'un produit, ses caractéristiques ou obtenir des conseils.")

        # Affichage de l'historique de discussion
        for speaker, message in st.session_state.chat_history:
            with st.chat_message(speaker):
                st.write(message)

        if prompt := st.chat_input("Ex : Quel type d'embout utiliser pour des volumes de 20 à 200 µl ?"):
            # Enregistrement et affichage de la question de l'utilisateur
            st.session_state.chat_history.append(("user", prompt))
            with st.chat_message("user"):
                st.write(prompt)

            # Génération et affichage de la réponse IA
            with st.chat_message("assistant"):
                with st.spinner("Recherche d'informations dans le catalogue..."):
                    context_data = data.to_string()
                    ai_reply = ask_ai(prompt, context_data)
                    st.write(ai_reply)
                    st.session_state.chat_history.append(("assistant", ai_reply))
