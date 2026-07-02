import streamlit as st
import pandas as pd
import smtplib
import requests
import unicodedata
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

st.set_page_config(
    page_title="Gestion & Demandes Plastique — INMED",
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

    /* Indicateurs de stock */
    .stock-badge-ok {
        background-color: #def7ec;
        color: #03543f;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stock-badge-low {
        background-color: #fdf2f2;
        color: #9b1c1c;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stock-badge-none {
        background-color: #f3f4f6;
        color: #4b5563;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6j8ofGR_sogNbwOjGZaX3v7KsswlNiXcIjjDBA5p8gg8SDyUmXBOgr0lGGu3G9SDkqytF_GBCXNMb/pub?output=csv"
LOCAL_STOCK_FILE = "stock_physique_inmed.csv"
MOT_DE_PASSE_GESTION = "INMED2026" 
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

@st.cache_data(ttl=10)
def load_data(reload_trigger):
    """Charge les données depuis le fichier CSV local ou l'initialise depuis Google Sheets."""
    if os.path.exists(LOCAL_STOCK_FILE):
        try:
            return pd.read_csv(LOCAL_STOCK_FILE)
        except Exception as e:
            st.error(f"Erreur de lecture du stock local : {e}")
            
    # Initialisation première fois ou si fichier supprimé
    try:
        df = pd.read_csv(SHEET_URL)
        # Détection d'une colonne de stock existante, ou création par défaut
        col_stock = next((c for c in df.columns if c.lower() in ["stock", "quantite", "quantite en stock", "qté"]), None)
        if not col_stock:
            df["Stock"] = 100  # On initialise par défaut à 100 unités si non spécifié
        else:
            df = df.rename(columns={col_stock: "Stock"})
        
        # Sauvegarde sur le disque local
        df.to_csv(LOCAL_STOCK_FILE, index=False)
        return df
    except Exception as e:
        return str(e)

def save_local_data(df):
    """Sauvegarde le jeu de données modifié sur le disque de l'application."""
    df.to_csv(LOCAL_STOCK_FILE, index=False)
    st.cache_data.clear()

def normalize_string(s):
    """Supprime les accents et convertit en minuscules pour une recherche ultra-robuste."""
    if not isinstance(s, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    ).lower()

def send_basket_email(nom, basket):
    destinataire = "olivier.lassalle@inserm.fr"
    sender = st.secrets.get("INSERM_EMAIL", "olivier.lassalle@inserm.fr")
    password = st.secrets.get("INSERM_PASSWORD", "")
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = destinataire
    msg['Subject'] = f"🧪 Prélèvement de matériel Plastique — {nom}"
    
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
            <h2 style="color: #1e293b; margin-top: 0; font-size: 1.5rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px;">🧪 Demande de prélèvement de matériel Plastique</h2>
            <p style="font-size: 1rem; color: #475569; margin: 15px 0;"><strong>Prélevé par :</strong> {nom}</p>
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
                Généré automatiquement par le Portail de Demandes Plastique INMED. Les niveaux de stock de l'inventaire numérique ont été mis à jour de façon synchrone.
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

def ask_ai(question, context):
    if not GROQ_API_KEY:
        return "⚠️ La clé API Groq n'est pas configurée dans les Secrets Streamlit."
    
    prompt = f"""Tu es l'assistant IA officiel du stock de consommables plastiques de l'institut INMED.
    Voici l'inventaire actuel en temps réel (contenant les quantités physiques disponibles pour chaque article) sous forme de texte brut :
    {context}
    
    Réponds de manière professionnelle, courte et précise en français.
    Si l'utilisateur te demande un état de stock, une alerte ou l'emplacement d'un produit, effectue tes recherches et réponds de façon rigoureuse.
    
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
    col_desig = next((c for c in data.columns if c.lower() in ["désignation", "designation"]), "Désignation")
    col_cat = next((c for c in data.columns if c.lower() in ["catégorie", "categorie"]), "Catégorie")
    col_cond = next((c for c in data.columns if c.lower() in ["conditionnement", "conditionement"]), "Conditionnement")
    col_info = next((c for c in data.columns if c.lower() in ["informations", "information", "remarques"]), "Informations")
    col_ref = next((c for c in data.columns if c.lower() in ["ref fabricant", "reference fabricant", "référence fabricant", "ref"]), "Ref Fabricant")

    # En-tête principal de la marque INMED
    st.markdown('<div class="main-title">🧪 Portail Plastique INMED</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Gestion dynamique, suivi de stock et prélèvements en temps réel</div>', unsafe_allow_html=True)

    tab_cmd, tab_gest, tab_faq = st.tabs(["🛒 Saisie Prélèvements (Commander)", "🛠️ Suivi & Ajustement des Stocks", "🤖 Assistant IA (FAQ)"])

    with tab_cmd:
        col_select, col_search = st.columns([1, 2])
        cats = ["Toutes"] + sorted(data[col_cat].dropna().unique().tolist())
        
        with col_select:
            cat_select = st.selectbox("📁 Filtrer par catégorie :", cats)
        with col_search:
            search_query = st.text_input("🔍 Rechercher un article par mot-clé :", placeholder="Ex : Flasque, Embout, Tube...")

        # Application des filtres
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
                stock = int(filtered_df.loc[i].get("Stock", 0))
                info_text = f" — [{info}]" if pd.notna(info) and str(info).strip() not in ["", "nan", "None", "N/A"] else ""
                return f"{desig} — Réf: {ref} (En stock : {stock} u.){info_text}"

            selected_idx = st.selectbox(
                "Choisir le produit précis dans la liste :", 
                options=filtered_df.index, 
                format_func=format_item_with_info
            )
            
            selected_item = data.loc[selected_idx]
            current_stock = int(selected_item.get("Stock", 0))
            
            # Présentation des détails avec badges de stock
            detail_col1, detail_col2, detail_col3 = st.columns(3)
            with detail_col1:
                st.info(f"📦 **Conditionnement :** {selected_item.get(col_cond, 'Non spécifié')}")
            with detail_col2:
                st.warning(f"ℹ️ **Informations :** {selected_item.get(col_info, 'Aucune remarque')}")
            with detail_col3:
                if current_stock > 15:
                    st.markdown(f'<div class="stock-badge-ok">🟢 Stock suffisant : {current_stock} unités</div>', unsafe_allow_html=True)
                elif current_stock > 0:
                    st.markdown(f'<div class="stock-badge-low">⚠️ Stock critique : {current_stock} unités restantes</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="stock-badge-none">🔴 En rupture de stock : {current_stock} unités</div>', unsafe_allow_html=True)

            qty = st.number_input("Quantité prélevée :", min_value=1, value=1, step=1)
            
            if st.button("➕ Ajouter l'article au panier", use_container_width=True):
                # Vérification de sécurité du stock
                if qty > current_stock:
                    st.error(f"❌ Impossible d'ajouter : le stock physique disponible n'est que de {current_stock} unités.")
                else:
                    # Ajout temporaire au panier
                    st.session_state.basket.append({
                        'index': selected_idx,
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
                        <div class="cart-item-qty">Qté demandée : {item['qty']}</div>
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
                st.markdown("#### 🚀 Valider le prélèvement")
                nom_demandeur = st.text_input("Saisissez votre Nom et Prénom :", placeholder="Ex : Marie Durant")
                
                if st.button("📧 Confirmer le prélèvement et envoyer par e-mail", type="primary", use_container_width=True):
                    if nom_demandeur.strip():
                        with st.spinner("Mise à jour en cours de l'inventaire numérique et envoi du courriel..."):
                            if send_basket_email(nom_demandeur.strip(), st.session_state.basket):
                                # Déduction effective des stocks physiques
                                for b_item in st.session_state.basket:
                                    idx_to_update = b_item['index']
                                    qty_deducted = b_item['qty']
                                    data.at[idx_to_update, 'Stock'] = max(0, int(data.at[idx_to_update, 'Stock']) - qty_deducted)
                                
                                # Enregistrement des données mises à jour
                                save_local_data(data)
                                
                                st.success(f"🎉 Stock mis à jour ! Demande enregistrée avec succès au nom de {nom_demandeur}.")
                                st.balloons()
                                st.session_state.basket = []
                                st.rerun()
                    else:
                        st.error("⚠️ Veuillez renseigner votre nom avant de valider.")
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
                st.markdown("Double-cliquez directement sur la colonne **'Stock'** du tableau ci-dessous pour ajuster manuellement les quantités physiques.")
            with col_admin_logout:
                if st.button("🔒 Déconnexion", use_container_width=True):
                    st.session_state.auth_gest = False
                    st.rerun()

            # Rendu de l'éditeur interactif pour modifier les stocks à la volée
            edited_data = st.data_editor(
                data,
                use_container_width=True,
                hide_index=True,
                disabled=[c for c in data.columns if c != "Stock"]  # Bloque l'édition des autres colonnes
            )
            
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button("💾 Sauvegarder les modifications manuelles de stock", type="primary", use_container_width=True):
                    save_local_data(edited_data)
                    st.success("Les modifications de stock ont été enregistrées avec succès !")
                    st.rerun()
            with col_save2:
                # Possibilité de télécharger le fichier d'inventaire complet à jour
                csv_file = edited_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Télécharger l'inventaire complet (CSV)",
                    data=csv_file,
                    file_name="inventaire_plastique_INMED.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            st.markdown("#### 🔄 Réinitialiser l'application")
            if st.button("⚠️ Forcer la resynchronisation avec Google Sheets (écrase le stock actuel)", use_container_width=True):
                if os.path.exists(LOCAL_STOCK_FILE):
                    os.remove(LOCAL_STOCK_FILE)
                st.session_state.reload_key += 1
                st.cache_data.clear()
                st.success("L'inventaire a été re-téléchargé et restauré depuis le tableur d'origine !")
                st.rerun()

    with tab_faq:
        st.subheader("🤖 Assistant virtuel du stock")
        st.write("Interrogez l'intelligence artificielle pour connaître l'état des stocks ou l'emplacement d'un produit.")

        # Affichage de l'historique
        for speaker, message in st.session_state.chat_history:
            with st.chat_message(speaker):
                st.write(message)

        if prompt := st.chat_input("Ex : Y a-t-il des flasques en rupture de stock ?"):
            st.session_state.chat_history.append(("user", prompt))
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyse du stock en cours..."):
                    context_data = data.to_string()
                    ai_reply = ask_ai(prompt, context_data)
                    st.write(ai_reply)
                    st.session_state.chat_history.append(("assistant", ai_reply))
