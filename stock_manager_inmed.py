import streamlit as st
import pandas as pd
import smtplib
import requests
import unicodedata
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Demandes Plastique — INMED",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS personnalisé injecté pour moderniser l'application
st.markdown("""
<style>
    /* Style global */
    .stApp {
        background-color: #fafbfc;
    }
    
    /* Titre principal */
    .main-title {
        color: #1e293b;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
    }
    
    /* Sous-titre */
    .subtitle {
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Cartes d'articles du panier */
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

def normalize_string(s):
    """Supprime les accents et convertit en minuscules pour une recherche ultra-robuste."""
    if not isinstance(s, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    ).lower()

# --- FONCTION D'ENVOI D'E-MAIL ---
def send_basket_email(nom, basket):
    destinataire = "olivier.lassalle@inserm.fr"
    sender = st.secrets.get("INSERM_EMAIL", "olivier.lassalle@inserm.fr")
    password = st.secrets.get("INSERM_PASSWORD", "")
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = destinataire
    msg['Subject'] = f"🧪 Nouvelle demande de matériel Plastique — {nom}"
    
    html_items = ""
    for item in basket:
        html_items += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 12px; font-weight: 600; color: #0f172a;">{item['designation']}</td>
            <td style="padding: 12px; text-align: center;"><span style="background: #eff6ff; color: #1d4ed8; padding: 4px 10px; border-radius: 999px; font-weight: bold;">{item['qty']}</span></td>
            <td style="padding: 12px; color: #64748b; font-size: 0.90rem;">{item['cond']}</td>
            <td style="padding: 12px; color: #64748b; font-size: 0.90rem;">{item['ref_fab']}</td>
        </tr>
        """
        
    body = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; padding: 20px; margin: 0;">
        <div style="max-width: 650px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 30px; margin: auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
            <h2 style="color: #1e293b; margin-top: 0; font-size: 1.5rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px;">🧪 Nouvelle demande de matériel Plastique</h2>
            <p style="font-size: 1rem; color: #475569; margin: 15px 0;"><strong>Demandeur :</strong> {nom}</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #f1f5f9; text-align: left; border-bottom: 2px solid #cbd5e1;">
                        <th style="padding: 12px; color: #475569;">Article</th>
                        <th style="padding: 12px; text-align: center; color: #475569;">Quantité</th>
                        <th style="padding: 12px; color: #475569;">Cond.</th>
                        <th style="padding: 12px; color: #475569;">Réf.</th>
                    </tr>
                </thead>
                <tbody>
                    {html_items}
                </tbody>
            </table>
            <div style="margin-top: 30px; font-size: 0.8rem; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                Généré automatiquement par le Portail de Demandes Plastique INMED.
            </div>
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
        st.error(f"❌ Erreur d'envoi du mail via smtp.inserm.fr : {e}")
        return False

# --- ASSISTANT VIRTUEL (IA) ---
def ask_ai(question, context):
    if not GROQ_API_KEY:
        return "⚠️ La clé API Groq n'est pas configurée dans les Secrets Streamlit."
    
    prompt = f"""Tu es l'assistant IA officiel du stock de consommables plastiques de l'institut INMED.
    Voici l'inventaire actuel en temps réel sous forme de texte brut :
    {context}
    
    Réponds de manière professionnelle, courte et précise en français.
    Si un utilisateur te demande l'emplacement ou la référence d'un produit, cherche-le soigneusement dans l'inventaire ci-dessus.
    
    Question utilisateur : {question}
    """
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            },
            timeout=10
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erreur de communication avec le cerveau de l'IA : {str(e)}"

# Initialisation de l'état de la session
if 'reload_key' not in st.session_state: st.session_state.reload_key = 0
if 'auth_gest' not in st.session_state: st.session_state.auth_gest = False
if 'basket' not in st.session_state: st.session_state.basket = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

data = load_data(st.session_state.reload_key)

if isinstance(data, str):
    st.error(f"❌ Impossible d'accéder aux données : {data}")
elif data.empty:
    st.warning("⚠️ L'inventaire importé est vide.")
else:
    # Détection automatique des colonnes pour tolérer les variations d'accents du fichier Sheets
    col_desig = next((c for c in data.columns if c.lower() in ["désignation", "designation"]), "Désignation")
    col_cat = next((c for c in data.columns if c.lower() in ["catégorie", "categorie"]), "Catégorie")
    col_cond = next((c for c in data.columns if c.lower() in ["conditionnement", "conditionement"]), "Conditionnement")
    col_info = next((c for c in data.columns if c.lower() in ["informations", "information", "remarques"]), "Informations")
    col_ref = next((c for c in data.columns if c.lower() in ["ref fabricant", "reference fabricant", "référence fabricant", "ref"]), "Ref Fabricant")

    # En-tête principal moderne
    st.markdown('<div class="main-title">🧪 Portail Plastique INMED</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Commandes internes, gestion de l\'inventaire et assistant logistique</div>', unsafe_allow_html=True)

    # Déclaration des onglets
    tab_cmd, tab_gest, tab_faq = st.tabs(["🛒 Commander", "🛠️ Gestion de l'Inventaire", "🤖 Assistant IA (FAQ)"])

    with tab_cmd:
        # CORRECTION : Déclaration correcte des colonnes de recherche !
        col_select, col_search = st.columns([1, 2])
        cats = ["Toutes"] + sorted(data[col_cat].dropna().unique().tolist())
        
        with col_select:
            cat_select = st.selectbox("📁 Filtrer par catégorie :", cats)
        with col_search:
            search_query = st.text_input("🔍 Rechercher un article par mot-clé :", placeholder="Ex : Flasque, Embout, Tube...")

        # Application des filtres avec tolérance aux accents et à la casse
        filtered_df = data if cat_select == "Toutes" else data[data[col_cat] == cat_select]
        if search_query:
            query_norm = normalize_string(search_query)
            filtered_df = filtered_df[
                filtered_df[col_desig].apply(lambda x: query_norm in normalize_string(str(x)))
            ]

        if not filtered_df.empty:
            st.markdown("### 1. Sélectionner l'article et la quantité")
            
            def format_item_with_info(i):
                desig = filtered_df.loc[i, col_desig]
                ref = filtered_df.loc[i].get(col_ref, 'N/A')
                info = filtered_df.loc[i].get(col_info, '')
                # S'assure que l'information est valide et non vide avant de l'ajouter
                info_text = f" — [{info}]" if pd.notna(info) and str(info).strip() not in ["", "nan", "None", "N/A"] else ""
                return f"{desig} — Réf: {ref}{info_text}"

            selected_idx = st.selectbox(
                "Choisir le produit précis dans la liste :", 
                options=filtered_df.index, 
                format_func=format_item_with_info
            )
            
            selected_item = data.loc[selected_idx]
            
            # Présentation des détails
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.info(f"📦 **Conditionnement :** {selected_item.get(col_cond, 'Non spécifié')}")
            with detail_col2:
                st.warning(f"ℹ️ **Informations :** {selected_item.get(col_info, 'Aucune remarque')}")

            qty = st.number_input("Quantité souhaitée :", min_value=1, value=1, step=1)
            
            if st.button("➕ Ajouter l'article au panier", use_container_width=True):
                st.session_state.basket.append({
                    'designation': selected_item[col_desig],
                    'qty': qty,
                    'cond': selected_item.get(col_cond, 'N/A'),
                    'info': selected_item.get(col_info, 'N/A'),
                    'ref_fab': selected_item.get(col_ref, 'N/A')
                })
                st.toast(f"✅ Ajouté : {selected_item[col_desig]} (x{qty})", icon="🛒")
                st.rerun()
        else:
            st.error("Aucun article ne correspond à vos critères de recherche.")

        st.markdown("---")
        
        st.markdown("### 🛒 Votre panier actuel")
        
        if st.session_state.basket:
            for idx, item in enumerate(st.session_state.basket):
                col_item_desc, col_item_action = st.columns([6, 1])
                
                with col_item_desc:
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
        st.write("Interrogez l'intelligence artificielle pour connaître l'emplacement d'un produit ou ses caractéristiques.")

        # Affichage de l'historique
        for speaker, message in st.session_state.chat_history:
            with st.chat_message(speaker):
                st.write(message)

        if prompt := st.chat_input("Ex : Quel type d'embout utiliser pour des volumes de 20 à 200 µl ?"):
            st.session_state.chat_history.append(("user", prompt))
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Recherche d'informations dans le catalogue..."):
                    context_data = data.to_string()
                    ai_reply = ask_ai(prompt, context_data)
                    st.write(ai_reply)
                    st.session_state.chat_history.append(("assistant", ai_reply))
