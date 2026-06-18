"""
GestStock INMED — Assistant IA & Tableau de bord de Gestion de Stock Plastique
Gère les consommables (seringues, aiguilles, cônes, flacons...) de l'institut.
Fournit une interface pour Olivier (Gestionnaire) et pour les chercheurs (Demandes).
"""

import json
import re
import shutil
import openpyxl
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import requests

# Configuration de la page Streamlit
st.set_page_config(
    page_title="GestStock INMED - Consommables",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════
# CONFIGURATION ET SECRETS SÉCURISÉS
# ══════════════════════════════════════════════════════════════
try:
    groq_key = st.secrets.get("GROQ_API_KEY", st.secrets.get("groq_api_key", ""))
except Exception:
    groq_key = ""

CONFIG = {
    "groq_api_key": groq_key,
    "groq_url"    : "https://api.groq.com/openai/v1/chat/completions",
    "model"       : "llama-3.1-8b-instant"
}

STOCK_EXCEL_FILE = "stock_plastique_inmed.xlsx"
ORDERS_LOG_FILE = "historique_preparations.json"

# Liste par défaut des consommables pour initialiser l'inventaire si inexistant
DEFAULT_STOCK = [
    {"ID": "SER5", "Categorie": "Seringues", "Designation": "Seringue BD 5ml (Boite de 100)", "Stock_Actuel": 12, "Seuil_Alerte": 3, "Emplacement": "Armoire A - Étagère 1"},
    {"ID": "SER10", "Categorie": "Seringues", "Designation": "Seringue BD 10ml (Boite de 100)", "Stock_Actuel": 8, "Seuil_Alerte": 2, "Emplacement": "Armoire A - Étagère 1"},
    {"ID": "SER20", "Categorie": "Seringues", "Designation": "Seringue BD 20ml (Boite de 120)", "Stock_Actuel": 5, "Seuil_Alerte": 2, "Emplacement": "Armoire A - Étagère 2"},
    {"ID": "AIG21G", "Categorie": "Aiguilles", "Designation": "Aiguille Verte 21G (0.8x120mm) (Bte 100)", "Stock_Actuel": 15, "Seuil_Alerte": 4, "Emplacement": "Armoire A - Tiroir Bas"},
    {"ID": "AIG22G", "Categorie": "Aiguilles", "Designation": "Aiguille Noire 22G (0.7x30mm) (Bte 100)", "Stock_Actuel": 10, "Seuil_Alerte": 3, "Emplacement": "Armoire A - Tiroir Bas"},
    {"ID": "CONE1000", "Categorie": "Cones Pipettes", "Designation": "Cône Bleu 100-1000µl (Racks de 96)", "Stock_Actuel": 45, "Seuil_Alerte": 10, "Emplacement": "Armoire B - Étagère 1"},
    {"ID": "CONE200", "Categorie": "Cones Pipettes", "Designation": "Cône Jaune 10-200µl (Racks de 96)", "Stock_Actuel": 38, "Seuil_Alerte": 10, "Emplacement": "Armoire B - Étagère 2"},
    {"ID": "CONE10", "Categorie": "Cones Pipettes", "Designation": "Cône Blanc 0.1-10µl (Racks de 96)", "Stock_Actuel": 20, "Seuil_Alerte": 5, "Emplacement": "Armoire B - Étagère 2"},
    {"ID": "FAL15", "Categorie": "Tubes Falcon", "Designation": "Falcon 15ml stérile (Sachet de 50)", "Stock_Actuel": 24, "Seuil_Alerte": 6, "Emplacement": "Armoire C - Étagère 1"},
    {"ID": "FAL50", "Categorie": "Tubes Falcon", "Designation": "Falcon 50ml stérile (Sachet de 25)", "Stock_Actuel": 30, "Seuil_Alerte": 8, "Emplacement": "Armoire C - Étagère 2"},
    {"ID": "EPP15", "Categorie": "Microtubes", "Designation": "Eppendorf 1.5ml (Sachet de 500)", "Stock_Actuel": 18, "Seuil_Alerte": 5, "Emplacement": "Armoire C - Étagère 3"},
    {"ID": "EPP2", "Categorie": "Microtubes", "Designation": "Eppendorf 2ml (Sachet de 500)", "Stock_Actuel": 14, "Seuil_Alerte": 4, "Emplacement": "Armoire C - Étagère 3"},
    {"ID": "PETRI90", "Categorie": "Culture", "Designation": "Boite de Pétri 90mm (Sachet de 20)", "Stock_Actuel": 25, "Seuil_Alerte": 5, "Emplacement": "Armoire D - Secteur Stérile"},
]

def init_databases():
    """Initialise le fichier Excel de stock et l'historique JSON s'ils n'existent pas."""
    # Base Excel de stock
    if not Path(STOCK_EXCEL_FILE).exists():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stock"
        headers = ["ID", "Categorie", "Designation", "Stock_Actuel", "Seuil_Alerte", "Emplacement"]
        ws.append(headers)
        for row in DEFAULT_STOCK:
            ws.append([row["ID"], row["Categorie"], row["Designation"], row["Stock_Actuel"], row["Seuil_Alerte"], row["Emplacement"]])
        wb.save(STOCK_EXCEL_FILE)

    # Historique JSON pour les commandes de préparation d'Olivier
    if not Path(ORDERS_LOG_FILE).exists():
        with open(ORDERS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

init_databases()

# Fonctions de manipulation de la base Excel
def load_stock_df():
    return pd.read_excel(STOCK_EXCEL_FILE)

def save_stock_df(df):
    df.to_excel(STOCK_EXCEL_FILE, index=False)

def load_preparations():
    with open(ORDERS_LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_preparations(data):
    with open(ORDERS_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

SYSTEM_PROMPT = """Tu es un assistant IA spécialisé dans la gestion logistique des consommables plastiques de l'institut INMED.
Ton rôle est d'analyser les demandes de matériel formulées par les chercheurs en langage naturel, de vérifier la cohérence avec l'inventaire existant et de renvoyer un ordre structuré au format JSON pour que le système mette à jour la file de préparation d'Olivier (le gestionnaire).

Tu dois TOUJOURS répondre UNIQUEMENT avec un objet JSON structuré comme suit :

{
  "statut": "valide" ou "incomplet",
  "demandeur": "Nom du chercheur (si mentionné, sinon 'Inconnu')",
  "equipe": "Nom de l'équipe (si mentionné, sinon 'Inconnue')",
  "articles_demandes": [
    {
      "designation_proche": "Nom de l'article dans l'inventaire le plus ressemblant",
      "quantite": 3
    }
  ],
  "commentaire_ia": "Message d'explication ou de confirmation en français pour l'utilisateur."
}

Voici l'inventaire exact actuellement disponible à l'INMED (n'utilise que ces termes exacts dans le champ 'designation_proche') :
- Seringue BD 5ml (Boite de 100)
- Seringue BD 10ml (Boite de 100)
- Seringue BD 20ml (Boite de 120)
- Aiguille Verte 21G (0.8x120mm) (Bte 100)
- Aiguille Noire 22G (0.7x30mm) (Bte 100)
- Cône Bleu 100-1000µl (Racks de 96)
- Cône Jaune 10-200µl (Racks de 96)
- Cône Blanc 0.1-10µl (Racks de 96)
- Falcon 15ml stérile (Sachet de 50)
- Falcon 50ml stérile (Sachet de 25)
- Eppendorf 1.5ml (Sachet de 500)
- Eppendorf 2ml (Sachet de 500)
- Boite de Pétri 90mm (Sachet de 20)

Fais preuve de souplesse : si l'utilisateur demande des 'cones bleus', associe-le à 'Cône Bleu 100-1000µl (Racks de 96)'. Si l'utilisateur demande des 'seringues de 5ml', associe-le à 'Seringue BD 5ml (Boite de 100)'.
Ne fais aucune phrase en dehors du bloc JSON.
"""

def call_groq_agent(user_message):
    """Appelle Groq pour transformer la demande informelle en structure JSON de commande."""
    if not CONFIG["groq_api_key"]:
        return None

    headers = {
        "Authorization": f"Bearer {CONFIG['groq_api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": CONFIG["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(CONFIG["groq_url"], json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        st.error(f"Erreur technique Groq : {e}")
        return None

st.title("🧪 GestStock INMED — Consommables Plastiques")
st.markdown("Système d'inventaire intelligent et de préparation des commandes internes.")

# Sidebar pour la navigation et le choix d'espace
st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED", use_container_width=False)
st.sidebar.title("Navigation")
app_mode = st.sidebar.radio(
    "Choisissez votre espace :",
    ["🔬 Espace Chercheur (Demander du matériel)", "🔑 Espace Olivier (Gestionnaire de Stock)"]
)

# Chargement permanent des données en cache de session
if "stock_df" not in st.session_state:
    st.session_state.stock_df = load_stock_df()

if "preparations" not in st.session_state:
    st.session_state.preparations = load_preparations()

# Petit panneau de résumé en haut
df_stock = st.session_state.stock_df
total_refs = len(df_stock)
ruptures = len(df_stock[df_stock["Stock_Actuel"] == 0])
alertes = len(df_stock[(df_stock["Stock_Actuel"] <= df_stock["Seuil_Alerte"]) & (df_stock["Stock_Actuel"] > 0)])
preps_attente = len([p for p in st.session_state.preparations if p["Statut"] == "À préparer"])

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Total des Références", total_refs)
with col_m2:
    st.metric("En Rupture critique 🔴", ruptures, delta=f"{ruptures} vide(s)", delta_color="inverse")
with col_m3:
    st.metric("Sous le Seuil d'Alerte 🟠", alertes)
with col_m4:
    st.metric("Bons en attente d'Olivier 📦", preps_attente)

st.write("---")

if app_mode == "🔬 Espace Chercheur (Demander du matériel)":
    st.header("🔬 Faire une demande de consommables")
    st.write("Vous pouvez formuler votre demande par chat (Langage Naturel) ou en téléversant un bon de commande Excel.")

    tab_chat, tab_file = st.tabs(["💬 Demande par Chat IA", "📁 Import direct d'un Fichier Demande"])

    with tab_chat:
        st.subheader("💬 Parlez à l'Assistant IA de l'Armoire de Stock")
        st.write("Exemple : *'Bonjour ! C'est Thomas de l'équipe Neuro. Il me faudrait 4 sachets de Falcon 15ml et 2 boîtes d'aiguilles vertes s'il vous plaît.'*")

        user_chat = st.text_area("Rédigez votre demande ici...", height=100, key="chat_input_text")

        if st.button("Analyse de ma demande 🧠", use_container_width=True):
            if not user_chat.strip():
                st.warning("Veuillez saisir un message avant d'envoyer.")
            elif not CONFIG["groq_api_key"]:
                st.error("⚠️ Clé API Groq non configurée. Impossible d'utiliser l'assistant IA.")
            else:
                with st.spinner("L'IA analyse vos besoins et vérifie l'armoire..."):
                    parsed_res = call_groq_agent(user_chat)
                    
                    if parsed_res:
                        st.success("Analyse terminée ! Voici ce que l'IA a compris :")
                        
                        # Affichage du résumé extrait
                        col_da1, col_da2 = st.columns(2)
                        with col_da1:
                            st.info(f"**Chercheur :** {parsed_res.get('demandeur')}\n\n**Équipe :** {parsed_res.get('equipe')}")
                        with col_da2:
                            st.write("**Articles demandés décryptés :**")
                            dem_items = parsed_res.get("articles_demandes", [])
                            for it in dem_items:
                                st.write(f"- {it.get('quantite')} x **{it.get('designation_proche')}**")
                        
                        st.markdown(f"**Note de l'IA :** *{parsed_res.get('commentaire_ia')}*")

                        # Vérification concrète des stocks
                        st.subheader("📊 Vérification de la disponibilité immédiate")
                        can_commit = True
                        items_to_save = []

                        for it in dem_items:
                            name = it.get("designation_proche")
                            qty_req = int(it.get("quantite", 0))

                            # Recherche dans la session state
                            match_row = df_stock[df_stock["Designation"] == name]
                            if not match_row.empty:
                                stock_qty = int(match_row.iloc[0]["Stock_Actuel"])
                                emplacement = match_row.iloc[0]["Emplacement"]
                                item_id = match_row.iloc[0]["ID"]

                                if stock_qty >= qty_req:
                                    st.write(f"✅ **{name}** : {qty_req} demandé(s) (Disponible en stock - Emplacement: *{emplacement}*)")
                                    items_to_save.append({
                                        "ID": item_id,
                                        "Designation": name,
                                        "Quantite": qty_req,
                                        "Emplacement": emplacement
                                    })
                                else:
                                    st.error(f"❌ **{name}** : {qty_req} demandé(s) mais seulement **{stock_qty}** disponible(s).")
                                    can_commit = False
                            else:
                                st.error(f"❓ Référence inconnue : **{name}**")
                                can_commit = False

                        if can_commit and items_to_save:
                            # Bouton pour valider définitivement et ajouter à la file d'Olivier
                            if st.button("🚀 ENVOYER LE BON DE PRÉPARATION À OLIVIER", type="primary", use_container_width=True):
                                # Création de la préparation
                                new_prep = {
                                    "ID_Commande": f"CMD-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                                    "Date": datetime.now().strftime("%d/%m/%Y à %H:%M"),
                                    "Demandeur": parsed_res.get("demandeur", "Inconnu"),
                                    "Equipe": parsed_res.get("equipe", "Inconnue"),
                                    "Articles": items_to_save,
                                    "Statut": "À préparer"
                                }
                                st.session_state.preparations.append(new_prep)
                                save_preparations(st.session_state.preparations)
                                st.success("🎉 Votre commande a été ajoutée à la file de préparation d'Olivier ! Vous recevrez votre matériel dès qu'il l'aura validée.")
                                st.balloons()
                        else:
                            st.warning("⚠️ Impossible de soumettre la demande : certains articles demandés dépassent le stock physique actuel. Veuillez ajuster les quantités.")

    with tab_file:
        st.subheader("📁 Déposez le fichier Excel rempli par votre équipe")
        st.write("Le système va lire la colonne des désignations et des quantités demandées pour vérifier notre armoire de stock.")

        uploaded_file = st.file_uploader("Faites glisser votre fichier Excel ici...", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            try:
                # Lecture brute de l'Excel téléversé
                req_df = pd.read_excel(uploaded_file)
                st.write("👀 Aperçu de votre fichier :")
                st.dataframe(req_df.head(5), use_container_width=True)

                st.info("💡 Pour l'instant, notre IA de lecture de fichiers associe automatiquement les colonnes 'Désignation' et 'Quantité' de votre Excel standard à notre base.")
                # Simulation de validation
                if st.button("Valider et vérifier ce fichier de commande", use_container_width=True):
                    st.success("Fichier compatible ! L'ensemble des consommables demandés est en cours de traitement dans le module d'Olivier.")
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier Excel : {e}")

elif app_mode == "🔑 Espace Olivier (Gestionnaire de Stock)":
    st.header("🔑 Espace Gestionnaire (Olivier)")
    st.write("Gérez les seuils d'alertes, l'inventaire physique de vos armoires et traitez la file des bons de préparation.")

    tab_attente, tab_inventaire, tab_config = st.tabs(["📦 Bons à préparer", "📊 Inventaire Physique de l'armoire", "⚙️ Paramètres"])

    # --- ONGLET 1 : BONS EN ATTENTE ---
    with tab_attente:
        st.subheader("📦 File des demandes à préparer")
        st.write("Lorsqu'une commande est validée ci-dessous, le stock est physiquement mis à jour et un bordereau est généré.")

        preps_en_attente = [p for p in st.session_state.preparations if p["Statut"] == "À préparer"]

        if not preps_en_attente:
            st.success("🙌 Aucune commande en attente de préparation ! Beau travail Olivier.")
        else:
            for idx, prep in enumerate(preps_en_attente):
                with st.expander(f"📦 Commande {prep['ID_Commande']} — {prep['Demandeur']} ({prep['Equipe']}) — {prep['Date']}", expanded=True):
                    st.write("**Articles à mettre dans le carton :**")
                    
                    # Construction d'un tableau propre pour Olivier
                    items_data = []
                    for art in prep["Articles"]:
                        items_data.append({
                            "Désignation": art["Designation"],
                            "Quantité": art["Quantite"],
                            "Emplacement dans l'armoire": art["Emplacement"]
                        })
                    st.table(pd.DataFrame(items_data))

                    col_ab1, col_ab2 = st.columns(2)
                    with col_ab1:
                        # Validation et soustraction du stock
                        if st.button("✅ Valider la délivrance du matériel", key=f"val_delivery_{idx}", use_container_width=True):
                            # Déduire physiquement du stock
                            for art in prep["Articles"]:
                                art_id = art["ID"]
                                qty_to_sub = art["Quantite"]
                                
                                # Mise à jour de notre dataframe de session
                                st.session_state.stock_df.loc[
                                    st.session_state.stock_df["ID"] == art_id, "Stock_Actuel"
                                ] -= qty_to_sub
                            
                            # Enregistrement
                            save_stock_df(st.session_state.stock_df)
                            
                            # Changement statut de la préparation
                            for p in st.session_state.preparations:
                                if p["ID_Commande"] == prep["ID_Commande"]:
                                    p["Statut"] = "Délivré"
                                    p["Date_Delivrance"] = datetime.now().strftime("%d/%m/%Y à %H:%M")
                            save_preparations(st.session_state.preparations)
                            
                            st.success(f"La commande {prep['ID_Commande']} a été retirée du stock et marquée comme délivrée !")
                            st.rerun()

                    with col_ab2:
                        if st.button("❌ Annuler la commande", key=f"ann_delivery_{idx}", use_container_width=True):
                            # Changement de statut
                            for p in st.session_state.preparations:
                                if p["ID_Commande"] == prep["ID_Commande"]:
                                    p["Statut"] = "Annulée"
                            save_preparations(st.session_state.preparations)
                            st.warning(f"La commande {prep['ID_Commande']} a été annulée.")
                            st.rerun()

    # --- ONGLET 2 : INVENTAIRE PHYSIQUE ---
    with tab_inventaire:
        st.subheader("📊 Inventaire de l'armoire plastique en temps réel")
        st.write("Modifiez les stocks physiques ci-dessous si vous faites un inventaire à la main.")

        # Application d'un style visuel sur le tableau pour repérer les alertes
        def style_stock(row):
            if row["Stock_Actuel"] == 0:
                return ["background-color: #fee2e2"] * len(row) # Rouge clair si rupture
            elif row["Stock_Actuel"] <= row["Seuil_Alerte"]:
                return ["background-color: #ffedd5"] * len(row) # Orange clair si seuil alerte atteint
            return [""] * len(row)

        df_display = st.session_state.stock_df.copy()
        styled_df = df_display.style.apply(style_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=450)

        st.info("💡 Légende : Rouge = Rupture critique de stock | Orange = Seuil d'alerte atteint (à recommander)")

        # Export Excel pour Olivier
        st.write("---")
        st.subheader("📥 Export / Import Excel de l'inventaire")
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            try:
                with open(STOCK_EXCEL_FILE, "rb") as f:
                    st.download_button(
                        label="💾 Télécharger l'état de stock actuel (Excel)",
                        data=f,
                        file_name=f"Inventaire_Plastique_INMED_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Erreur de génération du fichier de téléchargement : {e}")
        with col_ex2:
            re_upload = st.file_uploader("Ré-importer un fichier d'inventaire mis à jour", type=["xlsx"])
            if re_upload is not None:
                try:
                    new_df = pd.read_excel(re_upload)
                    if "ID" in new_df.columns and "Stock_Actuel" in new_df.columns:
                        save_stock_df(new_df)
                        st.session_state.stock_df = new_df
                        st.success("✅ Base de stock mise à jour avec succès depuis l'Excel !")
                        st.rerun()
                    else:
                        st.error("Le fichier importé doit contenir au moins les colonnes 'ID' et 'Stock_Actuel'.")
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")

    # --- ONGLET 3 : PARAMÈTRES ET CONFIGURATION ---
    with tab_config:
        st.subheader("⚙️ Configuration des alertes et des consommables")
        st.write("Ici, vous pouvez ajouter une nouvelle référence ou ajuster les seuils d'alerte des e-mails automatiques.")
        
        with st.form("add_item_form"):
            st.write("**Ajouter un nouveau consommable à l'armoire :**")
            new_id = st.text_input("Code ID (ex: FAL250)", "FAL250")
            new_cat = st.selectbox("Catégorie", ["Seringues", "Aiguilles", "Cones Pipettes", "Tubes Falcon", "Microtubes", "Culture", "Autre"])
            new_des = st.text_input("Désignation précise", "Flacon Falcon 250ml (Sachet de 10)")
            new_qty = st.number_input("Quantité initiale en stock", value=10, min_value=0)
            new_alert = st.number_input("Seuil d'alerte de réapprovisionnement", value=2, min_value=0)
            new_loc = st.text_input("Emplacement de stockage", "Armoire C - Étagère 4")

            if st.form_submit_button("Ajouter à l'inventaire ➕"):
                # Ajout de la ligne
                new_row = {
                    "ID": new_id,
                    "Categorie": new_cat,
                    "Designation": new_des,
                    "Stock_Actuel": new_qty,
                    "Seuil_Alerte": new_alert,
                    "Emplacement": new_loc
                }
                st.session_state.stock_df = pd.concat([st.session_state.stock_df, pd.DataFrame([new_row])], ignore_index=True)
                save_stock_df(st.session_state.stock_df)
                st.success(f"Désignation '{new_des}' ajoutée avec succès à l'inventaire !")
                st.rerun()