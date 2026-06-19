"""
GestStock INMED — Gestion du Stock Plastique & Consommables
Analyse automatique des fichiers de demande Excel + Assistant IA (Groq Cloud API)
Espace de suivi pour le gestionnaire de stock (Olivier)
"""

import json
import re
import io
import pandas as pd
import openpyxl
import requests
import streamlit as st
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# 1. CONFIGURATION ET SECRETS
# ══════════════════════════════════════════════════════════════
try:
    groq_key = st.secrets.get("GROQ_API_KEY", st.secrets.get("groq_api_key", ""))
except Exception:
    groq_key = ""

CONFIG = {
    "groq_api_key": groq_key,
    "groq_url"    : "https://api.groq.com/openai/v1/chat/completions",
    "model"       : "llama-3.1-8b-instant",
    "admin_pass"  : "inmed2026", # Mot de passe simple pour l'espace d'Olivier
}

# ══════════════════════════════════════════════════════════════
# 2. BASE DE DONNÉES DES ARTICLES (Issue de votre fichier Excel)
# ══════════════════════════════════════════════════════════════
INITIAL_STOCK = [
    # --- FILTRATION ---
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 150 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU01RE", "stock": 15, "seuil_alerte": 3},
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 250 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU02RE", "stock": 20, "seuil_alerte": 4},
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 500 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU05RE", "stock": 18, "seuil_alerte": 4},
    {"categorie": "FILTRATION", "designation": "Filtres seringue GP 33 mm, 0,22 µm", "cdt": "50 dans 1 boite", "ref_fab": "SLGP033RS", "stock": 30, "seuil_alerte": 5},
    {"categorie": "FILTRATION", "designation": "Filtres seringue GV 13 mm, 0,2 µm", "cdt": "100 dans 1 sachet", "ref_fab": "SLGVX13NL", "stock": 25, "seuil_alerte": 5},
    {"categorie": "FILTRATION", "designation": "Filtres seringue HA 33mm, 0,45µm", "cdt": "Unité", "ref_fab": "SLHA033S6", "stock": 40, "seuil_alerte": 10},
    
    # --- HISTO ET ELECTROPHY ---
    {"categorie": "HISTO / ELECTROPHY", "designation": "Flacons bouchons blancs 40ml", "cdt": "100 ds sachet", "ref_fab": "TP30C-013", "stock": 50, "seuil_alerte": 10},
    {"categorie": "HISTO / ELECTROPHY", "designation": "Flacons bouchons rouges 125ml", "cdt": "Unité", "ref_fab": "TP52C-023", "stock": 60, "seuil_alerte": 12},
    
    # --- SCOTCH ---
    {"categorie": "SCOTCH", "designation": "Scotch couleur rouge", "cdt": "16 rouleaux/boite", "ref_fab": "clearline", "stock": 12, "seuil_alerte": 3},
    {"categorie": "SCOTCH", "designation": "Scotch couleur Bleu", "cdt": "16 rouleaux/boite", "ref_fab": "1889385", "stock": 8, "seuil_alerte": 2},
    {"categorie": "SCOTCH", "designation": "Scotch couleur jaune", "cdt": "16 rouleaux/boite", "ref_fab": "clearline", "stock": 10, "seuil_alerte": 2},
    {"categorie": "SCOTCH", "designation": "Scotch couleur blanc", "cdt": "16 rouleaux/boite", "ref_fab": "1889375", "stock": 14, "seuil_alerte": 3},
    
    # --- PESÉE ---
    {"categorie": "PESEE", "designation": "Coupelle de pesée bleue petite", "cdt": "500 par carton", "ref_fab": "045104", "stock": 8, "seuil_alerte": 2},
    {"categorie": "PESEE", "designation": "Coupelle de pesée bleue moyenne", "cdt": "500 par carton", "ref_fab": "045106", "stock": 10, "seuil_alerte": 2},
    {"categorie": "PESEE", "designation": "Coupelle de pesée bleue grande", "cdt": "500 par carton", "ref_fab": "045108", "stock": 7, "seuil_alerte": 1},
    {"categorie": "PESEE", "designation": "Coupelle de pesée blanche 40x40 petite", "cdt": "500 par carton", "ref_fab": "HS1420AA", "stock": 15, "seuil_alerte": 3},
]

# ══════════════════════════════════════════════════════════════
# 3. CONTEXTE POUR L'IA (SYSTEM PROMPT)
# ══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Tu es l'assistant intelligent du stock plastique de l'INMED.
Ton rôle est d'analyser les demandes des chercheurs rédigées en langage naturel pour en extraire les articles commandés.

Quand l'utilisateur s'adresse à toi pour commander, identifie les produits correspondants dans la base et réponds UNIQUEMENT avec un JSON au format suivant :

{
  "statut": "succes",
  "commandes": [
    {
      "designation": "Nom exact du produit dans la base",
      "quantite": 2,
      "unite": "boite ou unité"
    }
  ],
  "message": "Un petit récapitulatif sympa en français de ce que tu as compris."
}

Si l'utilisateur demande quelque chose qui n'est pas dans le catalogue, réponds simplement avec un message poli expliquant que le produit n'est pas répertorié.

Voici la liste des produits autorisés dans la base (respecte la désignation exacte) :
- "Stéricups GP O.22µm 150 ml"
- "Stéricups GP O.22µm 250 ml"
- "Stéricups GP O.22µm 500 ml"
- "Filtres seringue GP 33 mm, 0,22 µm"
- "Filtres seringue GV 13 mm, 0,2 µm"
- "Filtres seringue HA 33mm, 0,45µm"
- "Flacons bouchons blancs 40ml"
- "Flacons bouchons rouges 125ml"
- "Scotch couleur rouge"
- "Scotch couleur Bleu"
- "Scotch couleur jaune"
- "Scotch couleur blanc"
- "Coupelle de pesée bleue petite"
- "Coupelle de pesée bleue moyenne"
- "Coupelle de pesée bleue grande"
- "Coupelle de pesée blanche 40x40 petite"
"""

# ══════════════════════════════════════════════════════════════
# 4. INITIALISATION DE L'ÉTAT DE SESSION
# ══════════════════════════════════════════════════════════════
if "db_stock" not in st.session_state:
    st.session_state.db_stock = INITIAL_STOCK.copy()

if "commandes_attente" not in st.session_state:
    st.session_state.commandes_attente = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ══════════════════════════════════════════════════════════════
# 5. FONCTIONS DE PARSING EXCEL & RECHERCHE DES PRODUITS
# ══════════════════════════════════════════════════════════════
def parse_excel_demande(file_bytes):
    """Analyse la fiche Excel de demande plastique INMED téléversée par un chercheur"""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active # Prend la première feuille active
        
        # 1. Extraction des métadonnées (Ligne 1 de la fiche INMED)
        nom_chercheur = ws["A1"].value or "Non spécifié"
        destination = ws["B1"].value or "Équipe non spécifiée"
        date_demande = ws["E1"].value or datetime.today().strftime("%d/%m/%Y")
        
        # Nettoyage des chaînes de texte des métadonnées
        if isinstance(nom_chercheur, str):
            nom_chercheur = nom_chercheur.replace("NOM PRENOM :", "").strip()
        if isinstance(destination, str):
            destination = destination.replace("DESTINATION :", "").strip()
        if isinstance(date_demande, str):
            date_demande = date_demande.replace("DATE :", "").strip()
            
        articles_demandes = []
        
        # 2. Lecture des lignes à partir de la ligne 5 (après l'en-tête de désignation)
        for row in range(5, ws.max_row + 1):
            designation = ws[f"A{row}"].value
            info = ws[f"B{row}"].value
            qty = ws[f"H{row}"].value # Colonne H : "quantité demandée"
            
            if designation and qty and isinstance(qty, (int, float)) and qty > 0:
                full_name = f"{designation}"
                if info:
                    full_name += f" {info}"
                articles_demandes.append({
                    "raw_designation": full_name.strip(),
                    "quantite": int(qty)
                })
                
        return {
            "success": True,
            "chercheur": nom_chercheur,
            "equipe": destination,
            "date": date_demande,
            "items": articles_demandes
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def map_raw_to_db(raw_name):
    """Tente de mapper intelligemment une saisie utilisateur vers notre base de données"""
    raw_clean = raw_name.lower()
    
    # Raccourcis de correspondance intelligente
    mappings = {
        "stericup 150": "Stéricups GP O.22µm 150 ml",
        "stericup 250": "Stéricups GP O.22µm 250 ml",
        "stericup 500": "Stéricups GP O.22µm 500 ml",
        "filtre 33": "Filtres seringue GP 33 mm, 0,22 µm",
        "filtre 13": "Filtres seringue GV 13 mm, 0,2 µm",
        "filtre 0.45": "Filtres seringue HA 33mm, 0,45µm",
        "flacon blanc": "Flacons bouchons blancs 40ml",
        "flacon rouge": "Flacons bouchons rouges 125ml",
        "scotch rouge": "Scotch couleur rouge",
        "scotch bleu": "Scotch couleur Bleu",
        "scotch jaune": "Scotch couleur jaune",
        "scotch blanc": "Scotch couleur blanc",
        "coupelle bleue petite": "Coupelle de pesée bleue petite",
        "coupelle bleue moyenne": "Coupelle de pesée bleue moyenne",
        "coupelle bleue grande": "Coupelle de pesée bleue grande",
        "coupelle blanche": "Coupelle de pesée blanche 40x40 petite",
    }
    
    for key, val in mappings.items():
        if key in raw_clean:
            return val
            
    # Recherche exacte ou partielle
    for item in st.session_state.db_stock:
        if item["designation"].lower() in raw_clean or raw_clean in item["designation"].lower():
            return item["designation"]
            
    return None

# ══════════════════════════════════════════════════════════════
# 6. INTERFACE STREAMLIT
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

# Menu de navigation
onglet = st.sidebar.radio(
    "🧭 Navigation", 
    ["👋 Espace Chercheurs (Demandes)", "🔑 Espace Olivier (Gestionnaire)"]
)

# ══════════════════════════════════════════════════════════════
# ONGLET 1 : ESPACE CHERCHEURS (DÉPÔT DES DEMANDES)
# ══════════════════════════════════════════════════════════════
if onglet == "👋 Espace Chercheurs (Demandes)":
    st.header("🧪 Dépôt de demande de consommables plastiques")
    st.write("Bienvenue sur la plateforme de commande. Vous pouvez déposer votre demande de deux manières différentes :")

    tab1, tab2, tab3 = st.tabs([
        "📥 Déposer votre Fiche Excel", 
        "💬 Demander en écrivant à l'IA", 
        "📋 Voir le catalogue disponible"
    ])
    
    # --- OPTION 1 : GLISSER-DÉPOSER LE FICHIER EXCEL ---
    with tab1:
        st.subheader("Importation de votre Fiche Excel")
        st.write("Faites simplement glisser votre fichier `Fiche demande labo plastique` complété ci-dessous.")
        
        uploaded_file = st.file_uploader("Choisissez un fichier Excel (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            with st.spinner("Analyse du fichier en cours..."):
                file_bytes = uploaded_file.read()
                result = parse_excel_demande(file_bytes)
                
                if result["success"]:
                    st.success("✅ Fiche de demande lue avec succès !")
                    
                    # Affichage des métadonnées détectées
                    col_met1, col_met2, col_met3 = st.columns(3)
                    with col_met1:
                        st.info(f"👤 **Chercheur :** {result['chercheur']}")
                    with col_met2:
                        st.info(f"👥 **Destination :** {result['equipe']}")
                    with col_met3:
                        st.info(f"📅 **Date :** {result['date']}")
                    
                    # Construction du tableau de commande
                    parsed_items = []
                    found_any = False
                    
                    for row in result["items"]:
                        db_name = map_raw_to_db(row["raw_designation"])
                        if db_name:
                            parsed_items.append({
                                "designation": db_name,
                                "quantite": row["quantite"],
                                "disponible": "Oui"
                            })
                            found_any = True
                        else:
                            parsed_items.append({
                                "designation": f"⚠️ {row['raw_designation']} (Non trouvé dans le stock)",
                                "quantite": row["quantite"],
                                "disponible": "Inconnu"
                            })
                    
                    if found_any:
                        df_preview = pd.DataFrame(parsed_items)
                        st.dataframe(df_preview, use_container_width=True)
                        
                        # Bouton de soumission finale
                        if st.button("🚀 Soumettre ma demande à Olivier", use_container_width=True, type="primary"):
                            # Enregistrement de la commande dans la file d'attente globale
                            st.session_state.commandes_attente.append({
                                "id": len(st.session_state.commandes_attente) + 1,
                                "chercheur": result["chercheur"],
                                "equipe": result["equipe"],
                                "date": result["date"],
                                "items": [item for item in parsed_items if "⚠️" not in item["designation"]],
                                "statut": "En attente"
                            })
                            st.balloons()
                            st.success("✅ Votre commande a bien été enregistrée et transmise à Olivier. Vous pouvez aller récupérer vos consommables !")
                    else:
                        st.warning("Aucun article avec une quantité demandée supérieure à 0 n'a été détecté dans votre fichier Excel.")
                else:
                    st.error(f"Impossible de lire le fichier Excel : {result['error']}")

    # --- OPTION 2 : ASSISTANT IA DISCUSSION ---
    with tab2:
        st.subheader("Commandez en parlant naturellement à l'IA")
        st.write("Exemple : *'Salut Olivier (via l'IA), j'aurais besoin de 2 cartons de stéricups 250ml et un scotch rouge pour l'équipe Neuro s'il te plaît'*")
        
        # Zone de discussion
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.write(chat["content"])
                
        if user_prompt := st.chat_input("Écrivez votre demande ici..."):
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            
            # Appel à l'API Groq Cloud
            if not groq_key:
                st.error("L'IA n'est pas configurée. Veuillez ajouter votre `GROQ_API_KEY` dans les Secrets de Streamlit.")
            else:
                with st.spinner("L'assistant IA de stock analyse votre demande..."):
                    payload = {
                        "model": CONFIG["model"],
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                    try:
                        r = requests.post(
                            CONFIG["groq_url"], 
                            json=payload, 
                            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                            timeout=25
                        )
                        r.raise_for_status()
                        ia_response = r.json()["choices"][0]["message"]["content"]
                        data_json = json.loads(ia_response)
                        
                        msg_ia = data_json.get("message", "Demande enregistrée.")
                        st.session_state.chat_history.append({"role": "assistant", "content": msg_ia})
                        
                        # Si l'IA a détecté des articles valides
                        if "commandes" in data_json and data_json["commandes"]:
                            st.info("📦 **Articles détectés par l'IA :**")
                            df_ia = pd.DataFrame(data_json["commandes"])
                            st.dataframe(df_ia, use_container_width=True)
                            
                            nom_user = st.text_input("Votre Nom complet :", placeholder="ex: Jean Dupont")
                            equipe_user = st.text_input("Votre Équipe / Destination :", placeholder="ex: Équipe Neuro")
                            
                            if st.button("🚀 Confirmer et soumettre cette commande"):
                                if nom_user and equipe_user:
                                    # Envoi en file d'attente
                                    st.session_state.commandes_attente.append({
                                        "id": len(st.session_state.commandes_attente) + 1,
                                        "chercheur": nom_user,
                                        "equipe": equipe_user,
                                        "date": datetime.today().strftime("%d/%m/%Y"),
                                        "items": data_json["commandes"],
                                        "statut": "En attente"
                                    })
                                    st.success("✅ Commande enregistrée avec succès !")
                                    st.balloons()
                                else:
                                    st.warning("Veuillez renseigner votre Nom et votre Équipe pour finaliser l'envoi.")
                    except Exception as e:
                        st.error(f"Erreur technique de l'assistant IA : {e}")
            st.rerun()

    # --- OPTION 3 : CATALOGUE DE STOCK DISPONIBLE ---
    with tab3:
        st.subheader("📋 Consommables Plastiques Disponibles")
        df_catalogue = pd.DataFrame(st.session_state.db_stock)
        
        # Masquer les seuils et données critiques pour l'utilisateur public
        df_public = df_catalogue[["categorie", "designation", "cdt", "ref_fab"]].copy()
        
        st.dataframe(df_public, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# ONGLET 2 : ESPACE OLIVIER (SÉCURISÉ)
# ══════════════════════════════════════════════════════════════
elif onglet == "🔑 Espace Olivier (Gestionnaire)":
    st.header("🔑 Espace d'administration du stock")
    
    password = st.text_input("Saisissez le code d'accès administrateur :", type="password")
    
    if password == CONFIG["admin_pass"]:
        st.success("🔓 Accès administrateur autorisé.")
        
        adm_tab1, adm_tab2, adm_tab3 = st.tabs([
            "📥 File d'attente des commandes", 
            "📊 État du stock réel", 
            "⚙️ Outils d'inventaire"
        ])
        
        # --- ONGLETS ADM 1 : FILE D'ATTENTE DES COMMANDES ---
        with adm_tab1:
            st.subheader("📋 Commandes reçues à préparer")
            
            attente = [c for c in st.session_state.commandes_attente if c["statut"] == "En attente"]
            
            if not attente:
                st.write("☕ Aucune commande en attente de préparation pour le moment.")
            else:
                for cmd in attente:
                    with st.expander(f"📦 Commande #{cmd['id']} - {cmd['chercheur']} ({cmd['equipe']}) - {cmd['date']}"):
                        st.write("**Articles demandés :**")
                        df_cmd_items = pd.DataFrame(cmd["items"])
                        st.dataframe(df_cmd_items, use_container_width=True)
                        
                        col_val1, col_val2 = st.columns(2)
                        with col_val1:
                            if st.button("✅ Valider et déduire du Stock", key=f"val_{cmd['id']}", use_container_width=True):
                                # Déduction réelle des stocks
                                error_stock = False
                                error_msg = ""
                                
                                # Vérification préliminaire
                                for order_item in cmd["items"]:
                                    item_db = next((item for item in st.session_state.db_stock if item["designation"] == order_item["designation"]), None)
                                    if item_db:
                                        if item_db["stock"] < order_item["quantite"]:
                                            error_stock = True
                                            error_msg += f"\n- Stock insuffisant pour {order_item['designation']} (Demandé : {order_item['quantite']}, En Stock : {item_db['stock']})"
                                
                                if error_stock:
                                    st.error(f"Impossible de valider la commande : {error_msg}")
                                else:
                                    # Déduction finale
                                    for order_item in cmd["items"]:
                                        item_db = next((item for item in st.session_state.db_stock if item["designation"] == order_item["designation"]), None)
                                        if item_db:
                                            item_db["stock"] -= order_item["quantite"]
                                    cmd["statut"] = "Délivrée"
                                    st.success("✅ Commande validée. Stock déduit avec succès !")
                                    st.rerun()
                                    
                        with col_val2:
                            if st.button("❌ Annuler / Rejeter la commande", key=f"rej_{cmd['id']}", use_container_width=True):
                                cmd["statut"] = "Annulée"
                                st.warning("La commande a été marquée comme annulée.")
                                st.rerun()

        # --- ONGLETS ADM 2 : TABLEAU DU STOCK RÉEL ---
        with adm_tab2:
            st.subheader("📊 Tableau de bord d'inventaire")
            
            stock_data = []
            for item in st.session_state.db_stock:
                statut_color = "🟢 OK"
                if item["stock"] <= 0:
                    statut_color = "🔴 Rupture de Stock"
                elif item["stock"] <= item["seuil_alerte"]:
                    statut_color = "🟠 Alerte Seuil Bas"
                    
                stock_data.append({
                    "Catégorie": item["categorie"],
                    "Désignation": item["designation"],
                    "Conditionnement": item["cdt"],
                    "Réf. Fabricant": item["ref_fab"],
                    "Stock Actuel": item["stock"],
                    "Seuil d'Alerte": item["seuil_alerte"],
                    "État": statut_color
                })
                
            df_stock_adm = pd.DataFrame(stock_data)
            st.dataframe(df_stock_adm, use_container_width=True)

        # --- ONGLETS ADM 3 : OUTILS D'INVENTAIRE (EXPORT EXCEL / MODIFICATION DIRECTE) ---
        with adm_tab3:
            st.subheader("⚙️ Outils d'administration rapides")
            
            # Formulaire de réapprovisionnement direct
            st.write("**Recharger manuellement la quantité d'un produit :**")
            prod_selected = st.selectbox("Sélectionnez le consommable :", [p["designation"] for p in st.session_state.db_stock])
            qty_add = st.number_input("Quantité reçue en livraison :", min_value=1, value=10)
            
            if st.button("➕ Ajouter au Stock physique", use_container_width=True):
                item_db = next((item for item in st.session_state.db_stock if item["designation"] == prod_selected), None)
                if item_db:
                    item_db["stock"] += qty_add
                    st.success(f"✅ Nouveau stock de {prod_selected} mis à jour : **{item_db['stock']} unités**.")
                    st.rerun()

            st.write("---")
            
            # Export de l'inventaire en Excel
            st.write("**Exporter l'état de stock actuel pour vos archives ou commandes fournisseurs :**")
            df_export = pd.DataFrame(st.session_state.db_stock)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='État des Stocks')
            
            st.download_button(
                label="💾 Télécharger l'inventaire complet (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Inventaire_Plastique_INMED_{datetime.today().strftime('%d-%m-%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
    elif password != "" and password != CONFIG["admin_pass"]:
        st.error("❌ Code d'accès administrateur incorrect.")
