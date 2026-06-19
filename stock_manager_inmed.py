"""
GestStock INMED — Gestion du Stock Plastique & Consommables
Analyse automatique des fichiers de demande Excel + Assistant IA (Groq Cloud API)
Espace de suivi pour le gestionnaire de stock (Olivier) avec persistence et synchro Excel.
"""

import json
import re
import io
from pathlib import Path
import pandas as pd
import openpyxl
import requests
import streamlit as st
from datetime import datetime

try:
    groq_key = st.secrets.get("GROQ_API_KEY", st.secrets.get("groq_api_key", ""))
except Exception:
    groq_key = ""

CONFIG = {
    "groq_api_key": groq_key,
    "groq_url"    : "https://api.groq.com/openai/v1/chat/completions",
    "model"       : "llama-3.1-8b-instant",
    "admin_pass"  : "inmed2026", # Code d'accès administrateur pour l'espace d'Olivier
}

STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

# Catalogue de secours (au cas où aucun Excel et aucune sauvegarde n'existent)
BACKUP_STOCK = [
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 150 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU01RE", "stock": 15, "seuil_alerte": 3},
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 250 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU02RE", "stock": 20, "seuil_alerte": 4},
    {"categorie": "FILTRATION", "designation": "Stéricups GP O.22µm 500 ml", "cdt": "12 dans 1 carton", "ref_fab": "SCGPU05RE", "stock": 18, "seuil_alerte": 4},
]

def get_cell_value(ws, row, col):
    """
    💡 SOLUTION EXPERTE : Lit correctement la valeur d'une cellule, 
    même si elle fait partie d'une zone fusionnée (merged cell) dans Excel.
    """
    cell = ws.cell(row=row, column=col)
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            # Retourne la valeur de la cellule en haut à gauche de la fusion
            return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
    return cell.value

def detect_columns(ws):
    """
    🔍 DÉTECTION DYNAMIQUE : Parcourt les premières lignes de l'Excel pour repérer 
    les colonnes exactes de désignation, conditionnement, référence et quantité.
    """
    col_des = 1  # Par défaut Col A (Désignation)
    col_cdt = 2  # Par défaut Col B (Détail/Conditionnement)
    col_ref = 3  # Par défaut Col C (Réf Fabricant)
    col_qty = 8  # Par défaut Col H (Quantité demandée)
    
    # Scan des 10 premières lignes
    for r in range(1, 11):
        for c in range(1, 15):
            val = ws.cell(row=r, column=c).value
            if val and isinstance(val, str):
                val_upper = val.upper()
                if "DESIGNATION" in val_upper or "DÉSIGNATION" in val_upper or "ARTICLE" in val_upper:
                    col_des = c
                elif "CONDITIONNEMENT" in val_upper or "CDT" in val_upper or "CONDITION" in val_upper or "DÉTAIL" in val_upper or "DETAIL" in val_upper:
                    col_cdt = c
                elif "REF" in val_upper or "RÉF" in val_upper or "CODE" in val_upper or "FABRICANT" in val_upper:
                    col_ref = c
                elif "QUANTITÉ" in val_upper or "QUANTITE" in val_upper or "DEMAND" in val_upper or "QTY" in val_upper:
                    col_qty = c
                    
    return col_des, col_cdt, col_ref, col_qty

def save_stock_state(db_stock):
    """Sauvegarde l'état actuel du stock dans un fichier JSON pour la persistence"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(db_stock, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"⚠️ Impossible de sauvegarder l'état du stock : {e}")

def load_stock_state():
    """Charge le stock depuis la sauvegarde JSON, sinon le construit depuis l'Excel"""
    # 1. Tenter de charger la sauvegarde JSON existante (contient les stocks réels d'Olivier)
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass

    # 2. Si aucune sauvegarde n'existe, scanner l'Excel pour construire la base
    if Path(EXCEL_FILE).exists():
        try:
            wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
            ws = wb.active
            
            # Détection des coordonnées de colonnes
            col_des, col_cdt, col_ref, _ = detect_columns(ws)
            
            catalog = []
            current_category = "AUTRES"
            
            # Balayage des lignes de l'Excel à partir de la ligne 5
            for r in range(5, ws.max_row + 1):
                des = get_cell_value(ws, r, col_des)
                cdt = get_cell_value(ws, r, col_cdt)
                ref = get_cell_value(ws, r, col_ref)
                
                if des:
                    des_str = str(des).strip()
                    
                    # Nettoyage et formatage du conditionnement
                    cdt_str = ""
                    if cdt is not None:
                        if isinstance(cdt, float) and cdt.is_integer():
                            cdt_str = str(int(cdt))
                        else:
                            cdt_str = str(cdt).strip()
                            
                    # Nettoyage de la référence
                    ref_str = ""
                    if ref is not None:
                        ref_str = str(ref).strip()
                        if ref_str.upper() in ["NONE", "N/A", "NAN", "NULL"]:
                            ref_str = ""

                    # 💡 DÉTECTION EXPERTE DE CATÉGORIE :
                    # Une catégorie est caractérisée par une désignation non vide,
                    # mais un conditionnement (cdt) et une référence totalement vides.
                    if not cdt_str and not ref_str:
                        # On ignore les textes d'en-tête de formulaire administratifs
                        if any(x in des_str.upper() for x in ["NOM", "PRÉNOM", "PRENOM", "DESTINATION", "DATE", "ÉQUIPE", "EQUIPE", "SIGNATURE", "VISA"]):
                            continue
                        current_category = des_str
                        continue
                    
                    # Ajout de l'article au catalogue dynamique
                    catalog.append({
                        "categorie": current_category,
                        "designation": des_str,
                        "cdt": cdt_str if cdt_str else "Unité",
                        "ref_fab": ref_str if ref_str else "N/A",
                        "stock": 50,         # Valeur initiale par défaut
                        "seuil_alerte": 5    # Seuil d'alerte par défaut
                    })
            
            if catalog:
                save_stock_state(catalog)
                return catalog
        except Exception as e:
            st.error(f"⚠️ Erreur lors de l'initialisation du catalogue depuis l'Excel : {e}")

    # 3. En dernier recours, charger la liste de secours brute
    return BACKUP_STOCK.copy()

def parse_excel_demande(file_bytes):
    """Analyse la fiche Excel de demande plastique INMED téléversée par un chercheur"""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        
        # Détection dynamique des colonnes
        col_des, col_cdt, col_ref, col_qty = detect_columns(ws)
        
        # Extraction intelligente des métadonnées (balayage des 4 premières lignes)
        nom_chercheur = "Non spécifié"
        destination = "Équipe non spécifiée"
        date_demande = datetime.today().strftime("%d/%m/%Y")
        
        for r in range(1, 5):
            for c in range(1, 10):
                val = ws.cell(row=r, column=c).value
                if val and isinstance(val, str):
                    val_clean = val.strip()
                    if "NOM" in val_clean.upper() or "PRÉNOM" in val_clean.upper():
                        nom_chercheur = val_clean.replace("NOM PRENOM :", "").replace("NOM :", "").replace("NOM PRENOM", "").replace(":", "").strip()
                    elif "DESTINATION" in val_clean.upper() or "EQUIPE" in val_clean.upper() or "ÉQUIPE" in val_clean.upper():
                        destination = val_clean.replace("DESTINATION :", "").replace("DESTINATION", "").replace(":", "").strip()
                    elif "DATE" in val_clean.upper():
                        date_demande = val_clean.replace("DATE :", "").replace("DATE", "").replace(":", "").strip()
        
        articles_demandes = []
        
        # Lecture des quantités demandées (Colonne de quantité détectée dynamiquement)
        for row in range(5, ws.max_row + 1):
            designation = get_cell_value(ws, row, col_des)
            info = get_cell_value(ws, row, col_cdt)
            qty = get_cell_value(ws, row, col_qty)
            
            if designation and qty and isinstance(qty, (int, float)) and qty > 0:
                full_name = f"{designation}"
                if info:
                    if isinstance(info, float) and info.is_integer():
                        info_str = str(int(info))
                    else:
                        info_str = str(info)
                    full_name += f" {info_str}"
                    
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
    raw_clean = raw_name.lower().strip()
    
    # Recherche exacte ou partielle dans la base de données réelle de l'application
    for item in st.session_state.db_stock:
        db_des = item["designation"].lower().strip()
        if raw_clean in db_des or db_des in raw_clean:
            return item["designation"]
            
    return None

if "db_stock" not in st.session_state:
    st.session_state.db_stock = load_stock_state()

if "commandes_attente" not in st.session_state:
    st.session_state.commandes_attente = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def get_dynamic_system_prompt():
    produits_puces = "\n".join([f"- \"{item['designation']}\"" for item in st.session_state.db_stock])
    return f"""Tu es l'assistant intelligent du stock plastique de l'INMED.
Ton rôle est d'analyser les demandes des chercheurs rédigées en langage naturel pour en extraire les articles commandés.

Quand l'utilisateur s'adresse à toi pour commander, identifie les produits correspondants dans la base et réponds UNIQUEMENT avec un JSON au format suivant :

{{
  "statut": "succes",
  "commandes": [
    {{
      "designation": "Nom exact du produit dans la base",
      "quantite": 2,
      "unite": "boite ou unité"
    }}
  ],
  "message": "Un petit récapitulatif sympa en français de ce que tu as compris."
}}

Si l'utilisateur demande quelque chose qui n'est pas dans le catalogue, réponds simplement avec un message poli expliquant que le produit n'est pas répertorié.

Voici la liste des produits autorisés dans la base (respecte la désignation exacte) :
{produits_puces}
"""

st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

onglet = st.sidebar.radio(
    "🧭 Navigation", 
    ["👋 Espace Chercheurs (Demandes)", "🔑 Espace Olivier (Gestionnaire)"]
)

if onglet == "👋 Espace Chercheurs (Demandes)":
    st.header("🧪 Dépôt de demande de consommables plastiques")
    st.write("Bienvenue sur la plateforme de commande de l'INMED. Choisissez l'une des méthodes ci-dessous pour soumettre votre demande :")

    tab1, tab2, tab3 = st.tabs([
        "📥 Déposer votre Fiche Excel", 
        "💬 Demander en écrivant à l'IA", 
        "📋 Voir le catalogue disponible"
    ])
    
    # --- OPTION 1 : GLISSER-DÉPOSER LE FICHIER EXCEL ---
    with tab1:
        st.subheader("Importation de votre Fiche Excel")
        st.write("Glissez-déposez simplement votre fichier `Fiche demande labo plastique 2025-2026.xlsx` rempli ci-dessous.")
        
        uploaded_file = st.file_uploader("Choisissez un fichier Excel (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            with st.spinner("Analyse de votre fichier Excel en cours..."):
                file_bytes = uploaded_file.read()
                result = parse_excel_demande(file_bytes)
                
                if result["success"]:
                    st.success("✅ Fiche lue avec succès !")
                    
                    col_met1, col_met2, col_met3 = st.columns(3)
                    with col_met1:
                        st.info(f"👤 **Chercheur :** {result['chercheur']}")
                    with col_met2:
                        st.info(f"👥 **Destination/Équipe :** {result['equipe']}")
                    with col_met3:
                        st.info(f"📅 **Date :** {result['date']}")
                    
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
                        
                        if st.button("🚀 Soumettre ma demande à Olivier", use_container_width=True, type="primary"):
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

    with tab2:
        st.subheader("Commandez en parlant naturellement à l'IA")
        st.write("Exemple : *'Salut Olivier (via l'IA), j'aurais besoin de 2 boîtes de stéricups 250ml et un scotch rouge pour l'équipe Neuro s'il te plaît'*")
        
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.write(chat["content"])
                
        if user_prompt := st.chat_input("Écrivez votre demande ici..."):
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            
            if not CONFIG["groq_api_key"]:
                st.error("L'IA n'est pas configurée. Veuillez ajouter votre `GROQ_API_KEY` dans les Secrets de Streamlit.")
            else:
                with st.spinner("L'assistant IA de stock analyse votre demande..."):
                    payload = {
                        "model": CONFIG["model"],
                        "messages": [
                            {"role": "system", "content": get_dynamic_system_prompt()},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                    try:
                        r = requests.post(
                            CONFIG["groq_url"], 
                            json=payload, 
                            headers={"Authorization": f"Bearer {CONFIG['groq_api_key']}", "Content-Type": "application/json"},
                            timeout=25
                        )
                        r.raise_for_status()
                        ia_response = r.json()["choices"][0]["message"]["content"]
                        data_json = json.loads(ia_response)
                        
                        msg_ia = data_json.get("message", "Demande enregistrée.")
                        st.session_state.chat_history.append({"role": "assistant", "content": msg_ia})
                        
                        if "commandes" in data_json and data_json["commandes"]:
                            st.info("📦 **Articles détectés par l'IA :**")
                            df_ia = pd.DataFrame(data_json["commandes"])
                            st.dataframe(df_ia, use_container_width=True)
                            
                            nom_user = st.text_input("Votre Nom complet :", placeholder="ex: Jean Dupont")
                            equipe_user = st.text_input("Votre Équipe / Destination :", placeholder="ex: Équipe Neuro")
                            
                            if st.button("🚀 Confirmer et soumettre cette commande"):
                                if nom_user and equipe_user:
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

    with tab3:
        st.subheader("📋 Consommables Plastiques Disponibles")
        df_catalogue = pd.DataFrame(st.session_state.db_stock)
        df_public = df_catalogue[["categorie", "designation", "cdt", "ref_fab"]].copy()
        
        # Filtre de recherche par catégorie
        categories_liste = ["Toutes"] + list(df_public["categorie"].unique())
        selected_cat = st.selectbox("Filtrer par catégorie :", categories_liste)
        
        if selected_cat != "Toutes":
            df_public = df_public[df_public["categorie"] == selected_cat]
            
        st.dataframe(df_public, use_container_width=True)

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
                                error_stock = False
                                error_msg = ""
                                
                                # Vérification préliminaire des quantités
                                for order_item in cmd["items"]:
                                    item_db = next((item for item in st.session_state.db_stock if item["designation"] == order_item["designation"]), None)
                                    if item_db:
                                        if item_db["stock"] < order_item["quantite"]:
                                            error_stock = True
                                            error_msg += f"\n- Stock insuffisant pour {order_item['designation']} (Demandé : {order_item['quantite']}, En Stock : {item_db['stock']})"
                                
                                if error_stock:
                                    st.error(f"Impossible de valider la commande : {error_msg}")
                                else:
                                    # Déduction finale des stocks et sauvegarde de l'état
                                    for order_item in cmd["items"]:
                                        item_db = next((item for item in st.session_state.db_stock if item["designation"] == order_item["designation"]), None)
                                        if item_db:
                                            item_db["stock"] -= order_item["quantite"]
                                    cmd["statut"] = "Délivrée"
                                    save_stock_state(st.session_state.db_stock)
                                    st.success("✅ Commande validée. Stock déduit avec succès !")
                                    st.rerun()
                                    
                        with col_val2:
                            if st.button("❌ Annuler / Rejeter la commande", key=f"rej_{cmd['id']}", use_container_width=True):
                                cmd["statut"] = "Annulée"
                                st.warning("La commande a été marquée comme annulée.")
                                st.rerun()

        with adm_tab2:
            st.subheader("📊 Tableau de bord d'inventaire")
            
            # Recherche rapide
            recherche = st.text_input("Rechercher un produit, catégorie ou référence :")
            
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
            
            # Application de la recherche
            if recherche:
                df_stock_adm = df_stock_adm[
                    df_stock_adm["Désignation"].str.contains(recherche, case=False, na=False) |
                    df_stock_adm["Catégorie"].str.contains(recherche, case=False, na=False) |
                    df_stock_adm["Réf. Fabricant"].str.contains(recherche, case=False, na=False)
                ]
                
            st.dataframe(df_stock_adm, use_container_width=True)

        with adm_tab3:
            st.subheader("⚙️ Ajustements & Exportations rapides")
            
            col_ajust1, col_ajust2 = st.columns(2)
            
            with col_ajust1:
                st.write("**Ajuster manuellement le stock d'un produit :**")
                prod_selected = st.selectbox("Sélectionnez le consommable :", [p["designation"] for p in st.session_state.db_stock])
                item_db = next((item for item in st.session_state.db_stock if item["designation"] == prod_selected), None)
                
                if item_db:
                    nv_stock = st.number_input("Nouveau niveau de stock physique :", min_value=0, value=item_db["stock"])
                    nv_seuil = st.number_input("Nouveau seuil d'alerte :", min_value=0, value=item_db["seuil_alerte"])
                    
                    if st.button("💾 Enregistrer l'ajustement", use_container_width=True):
                        item_db["stock"] = nv_stock
                        item_db["seuil_alerte"] = nv_seuil
                        save_stock_state(st.session_state.db_stock)
                        st.success(f"✅ Informations mises à jour pour **{prod_selected}** !")
                        st.rerun()
            
            with col_ajust2:
                st.write("**Ajouter une nouvelle référence manuellement :**")
                n_cat = st.text_input("Catégorie :", placeholder="ex: HISTO / ELECTROPHY")
                n_des = st.text_input("Désignation de l'article :", placeholder="ex: Tubes Eppendorf stérile 1.5ml")
                n_cdt = st.text_input("Conditionnement :", placeholder="ex: 500 par boîte")
                n_ref = st.text_input("Référence Fabricant :", placeholder="ex: EP15-ST")
                n_stock = st.number_input("Stock de départ :", min_value=0, value=50)
                n_seuil = st.number_input("Seuil d'alerte bas :", min_value=0, value=5)
                
                if st.button("➕ Ajouter la nouvelle référence au stock", use_container_width=True):
                    if n_cat and n_des:
                        st.session_state.db_stock.append({
                            "categorie": n_cat.upper().strip(),
                            "designation": n_des.strip(),
                            "cdt": n_cdt.strip() if n_cdt else "Unité",
                            "ref_fab": n_ref.strip() if n_ref else "N/A",
                            "stock": int(n_stock),
                            "seuil_alerte": int(n_seuil)
                        })
                        save_stock_state(st.session_state.db_stock)
                        st.success(f"✅ Nouveau produit '{n_des}' ajouté au catalogue !")
                        st.rerun()
                    else:
                        st.error("Veuillez renseigner au moins la Catégorie et la Désignation.")

            st.write("---")
            
            # Force de synchronisation dynamique depuis le fichier Excel
            st.write("**🔄 Synchroniser l'application avec l'Excel de GitHub :**")
            st.info("Cette action va re-scanner le fichier Excel officiel pour y chercher des nouveautés tout en préservant vos stocks actuels.")
            if st.button("⚙️ Lancer la synchronisation Excel", use_container_width=True):
                if Path(EXCEL_FILE).exists():
                    try:
                        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
                        ws = wb.active
                        col_des, col_cdt, col_ref, _ = detect_columns(ws)
                        
                        updated_catalog = []
                        current_category = "AUTRES"
                        for r in range(5, ws.max_row + 1):
                            des = get_cell_value(ws, r, col_des)
                            cdt = get_cell_value(ws, r, col_cdt)
                            ref = get_cell_value(ws, r, col_ref)
                            
                            if des:
                                des_str = str(des).strip()
                                
                                cdt_str = ""
                                if cdt is not None:
                                    if isinstance(cdt, float) and cdt.is_integer():
                                        cdt_str = str(int(cdt))
                                    else:
                                        cdt_str = str(cdt).strip()
                                        
                                ref_str = ""
                                if ref is not None:
                                    ref_str = str(ref).strip()
                                    if ref_str.upper() in ["NONE", "N/A", "NAN", "NULL"]:
                                        ref_str = ""
                                
                                # 💡 DÉTECTION EXPERTE ET ULTRA-PRÉCISE :
                                # Les catégories sont dorénavant détectées de manière purement logique :
                                # S'il y a un nom mais pas de conditionnement et pas de référence, c'est une catégorie !
                                if not cdt_str and not ref_str:
                                    if any(x in des_str.upper() for x in ["NOM", "PRENOM", "DESTINATION", "DATE", "EQUIPE", "SIGNATURE", "VISA"]):
                                        continue
                                    current_category = des_str
                                    continue
                                
                                # Recherche de correspondance de stock existant
                                matched_item = next((item for item in st.session_state.db_stock if item["designation"] == des_str), None)
                                current_stock_level = matched_item["stock"] if matched_item else 50
                                current_seuil_level = matched_item["seuil_alerte"] if matched_item else 5
                                    
                                updated_catalog.append({
                                    "categorie": current_category,
                                    "designation": des_str,
                                    "cdt": cdt_str if cdt_str else "Unité",
                                    "ref_fab": ref_str if ref_str else "N/A",
                                    "stock": current_stock_level,
                                    "seuil_alerte": current_seuil_level
                                })
                        
                        st.session_state.db_stock = updated_catalog
                        save_stock_state(updated_catalog)
                        st.success("✅ Synchronisation et nettoyage du catalogue réussis !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur de re-scan : {e}")
                else:
                    st.error("Fichier Excel source introuvable sur le dépôt.")
            
            st.write("---")
            
            # Exportation Excel pour inventaire
            st.write("**Exporter l'inventaire complet :**")
            df_export = pd.DataFrame(st.session_state.db_stock)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='État des Stocks')
            
            st.download_button(
                label="💾 Télécharger l'inventaire en Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Inventaire_Plastique_INMED_{datetime.today().strftime('%d-%m-%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
    elif password != "" and password != CONFIG["admin_pass"]:
        st.error("❌ Code d'accès administrateur incorrect.")
