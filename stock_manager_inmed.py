"""
GestStock INMED — Gestion du Stock Plastique & Consommables
Lecture intelligente des fichiers de demande Excel avec propagation des désignations vides
Édition directe en mode tableur (type Excel) stable et persistant, et assistant IA Groq
"""

import json
import re
import io
import unicodedata
from pathlib import Path
import pandas as pd
import openpyxl
import requests
import streamlit as st
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURATION ET CONSTANTES
# ══════════════════════════════════════════════════════════════
STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

try:
    groq_key = st.secrets.get("GROQ_API_KEY", st.secrets.get("groq_api_key", ""))
except Exception:
    groq_key = ""

CONFIG = {
    "groq_api_key": groq_key,
    "groq_url"    : "https://api.groq.com/openai/v1/chat/completions",
    "model"       : "llama-3.1-8b-instant",
    "admin_pass"  : "inmed2026", # Code d'accès pour l'espace d'Olivier
}

OFFICIAL_CATEGORIES = [
    "FILTRATION",
    "HISTO ET ELECTROPHY",
    "TUBES",
    "CULTURE CELLULAIRE",
    "POINTES OU TIPS",
    "SERINGUES ET AIGUILLES",
    "BACTÉRIO",
    "PCR",
    "DIVERS",
    "PESÉES"
]

# ══════════════════════════════════════════════════════════════
# FONCTIONS DE NETTOYAGE ET D'ANALYSE SEMANTIQUE
# ══════════════════════════════════════════════════════════════
def clean_text(text):
    if not text:
        return ""
    # Normalise (retire les accents et caractères spéciaux)
    s = str(text).lower()
    s = "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    # Conserve uniquement les lettres
    return re.sub(r'[^a-z]', '', s)

def detect_category(designation_val, info_val, cdt_val, ref_val):
    """
    Détermine si une ligne Excel correspond à un en-tête de catégorie.
    Une catégorie est caractérisée par une désignation non vide, mais toutes les autres colonnes vides.
    """
    if not designation_val:
        return None
        
    des_clean = designation_val.strip().upper()
    # Si d'autres colonnes de description de produit sont remplies, ce n'est pas une catégorie
    if info_val or cdt_val or ref_val:
        return None
        
    # Nettoyer les chiffres éventuels au début ("1. FILTRATION" -> "FILTRATION")
    des_clean = re.sub(r'^\d+[\s\.\-)]+', '', des_clean)
    
    # Dictionnaire de correspondance flexible
    cats_map = {
        "FILTRATION": ["FILTRATION", "FILTER"],
        "HISTO ET ELECTROPHY": ["HISTO", "ELECTROPHY", "ELECTROPHYS"],
        "TUBES": ["TUBES", "TUBE"],
        "CULTURE CELLULAIRE": ["CULTURE", "CELLULAIRE"],
        "POINTES OU TIPS": ["POINTES", "TIPS", "POINTE", "TIP"],
        "SERINGUES ET AIGUILLES": ["SERINGUES", "AIGUILLES", "SERINGUE", "AIGUILLE"],
        "BACTÉRIO": ["BACTERIO", "BACTÉRIO"],
        "PCR": ["PCR"],
        "DIVERS": ["DIVERS"],
        "PESÉES": ["PESEE", "PESEES", "PESÉES", "PESÉE"]
    }
    
    for official_name, keywords in cats_map.items():
        if any(kw in clean_text(des_clean) for kw in keywords):
            return official_name
            
    return None

def get_cell_value(ws, row, col):
    """Lit la valeur d'une cellule en gérant proprement les cellules fusionnées"""
    cell = ws.cell(row=row, column=col)
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            # Retourne la cellule maîtresse (en haut à gauche) du bloc fusionné
            return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
    return cell.value

# ══════════════════════════════════════════════════════════════
# PARSER EXCEL INTELLIGENT (AVEC PROPAGATION DES CELLULES VIDES)
# ══════════════════════════════════════════════════════════════
def import_excel_catalog(filepath):
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active
        
        catalog = []
        current_category = "DIVERS"
        last_valid_designation = ""
        
        # On commence à la ligne 5 (après la ligne d'en-tête "Designation, Informations...")
        for r in range(5, ws.max_row + 1):
            raw_des = get_cell_value(ws, r, 1) # Colonne A : Designation
            raw_info = get_cell_value(ws, r, 2) # Colonne B : Informations
            raw_cdt = get_cell_value(ws, r, 3) # Colonne C : Cdt
            raw_ref = get_cell_value(ws, r, 5) # Colonne E : Ref fabricant
            
            # Ligne complètement vide, on l'ignore
            if not raw_des and not raw_info and not raw_cdt and not raw_ref:
                continue
                
            # Détection et changement de catégorie
            cat_detected = detect_category(raw_des, raw_info, raw_cdt, raw_ref)
            if cat_detected:
                current_category = cat_detected
                last_valid_designation = "" # Réinitialisation de la désignation parente
                continue
                
            # Logique de carry-over (propagation) :
            # Si la colonne désignation est vide mais qu'on a des informations sur la ligne,
            # on récupère le dernier nom d'article parent mémorisé
            if raw_des and str(raw_des).strip() != "":
                last_valid_designation = str(raw_des).strip()
                
            final_designation = last_valid_designation
            if raw_info and str(raw_info).strip() != "":
                # On concatène les infos complémentaires (ex: "Stéricups GP" + "150 ml")
                if final_designation:
                    final_designation += f" - {str(raw_info).strip()}"
                else:
                    final_designation = str(raw_info).strip()
            
            # Si nous n'avons aucun nom à ce stade, on ignore la ligne
            if not final_designation:
                continue
                
            catalog.append({
                "categorie": current_category,
                "designation": final_designation,
                "cdt": str(raw_cdt).strip() if raw_cdt else "Unité",
                "ref_fab": str(raw_ref).strip() if raw_ref else "N/A",
                "stock": 50, # Stock de départ par défaut
                "seuil_alerte": 10
            })
            
        return {"success": True, "data": catalog}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ══════════════════════════════════════════════════════════════
# GESTION DES DONNÉES EN SESSION ET SAUVEGARDE
# ══════════════════════════════════════════════════════════════
def save_state_to_file():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.db_stock, f, ensure_ascii=False, indent=4)

def load_state():
    if Path(STATE_FILE).exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def apply_editor_changes(df_original, state_changes):
    """
    Applique de force les modifications d'édition de cellule, d'ajout 
    et de suppression d'un composant de tableur Streamlit sur un DataFrame.
    """
    res_df = df_original.copy()
    
    # 1. Application des cellules éditées
    for row_idx_str, edits in state_changes.get("edited_rows", {}).items():
        row_idx = int(row_idx_str)
        if row_idx < len(res_df):
            for col, val in edits.items():
                res_df.at[row_idx, col] = val
                
    # 2. Application des nouvelles lignes insérées
    for addition in state_changes.get("added_rows", []):
        new_row = {col: addition.get(col, "") for col in res_df.columns}
        # Valeurs par défaut pour les colonnes numériques obligatoires
        if not new_row.get("stock"): 
            new_row["stock"] = 0
        if not new_row.get("seuil_alerte"): 
            new_row["seuil_alerte"] = 10
        if not new_row.get("categorie"):
            new_row["categorie"] = "DIVERS"
        res_df = pd.concat([res_df, pd.DataFrame([new_row])], ignore_index=True)
        
    # 3. Application des lignes supprimées
    deletions = sorted([int(idx) for idx in state_changes.get("deleted_rows", [])], reverse=True)
    for idx in deletions:
        if idx < len(res_df):
            res_df = res_df.drop(res_df.index[idx]).reset_index(drop=True)
            
    return res_df

# Initialisation de la session
if "db_stock" not in st.session_state:
    st.session_state.db_stock = load_state()

if "commandes_attente" not in st.session_state:
    st.session_state.commandes_attente = []

if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0

# ══════════════════════════════════════════════════════════════
# INTERFACE GRAPHIQUE STREAMLIT
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
st.title("🧪 GestStock INMED — Gestionnaire de Stock")

# Menu principal
onglet = st.sidebar.radio("🧭 Menu principal", ["👋 Espace Chercheurs (Demandes)", "🔑 Espace Administration (Olivier)"])

# ──────────────────────────────────────────────────────────────
# ONGLET 1 : ESPACE CHERCHEURS (DEMANDES & CATALOGUE)
# ──────────────────────────────────────────────────────────────
if onglet == "👋 Espace Chercheurs (Demandes)":
    st.header("👋 Passer une commande de consommables plastiques")
    
    if not st.session_state.db_stock:
        st.warning("⚠️ L'inventaire est actuellement vide. Olivier doit d'abord synchroniser le fichier Excel dans son espace.")
    else:
        tab_demande, tab_cat = st.tabs(["📝 Formulaire de Demande Rapide", "📋 Consulter l'inventaire"])
        
        with tab_demande:
            st.write("Remplissez vos besoins ci-dessous pour soumettre votre demande à Olivier.")
            
            # Saisie des informations de la personne
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                nom_demande = st.text_input("Nom & Prénom :", placeholder="ex: Sophie Durand")
            with col_u2:
                equipe_demande = st.text_input("Destination / Équipe :", placeholder="ex: Équipe Neuro-Physio")
                
            # Sélection des articles
            st.write("---")
            st.write("**Ajouter des articles à votre demande :**")
            
            # Organisation par catégories pour faciliter la recherche
            categories_existantes = sorted(list(set(item["categorie"] for item in st.session_state.db_stock)))
            cat_choisie = st.selectbox("Sélectionnez une catégorie :", categories_existantes)
            
            articles_filtrés = [item for item in st.session_state.db_stock if item["categorie"] == cat_choisie]
            options_articles = {item["designation"]: item for item in articles_filtrés}
            
            art_choisi_nom = st.selectbox("Sélectionnez l'article :", list(options_articles.keys()))
            quantite_demandee = st.number_input("Quantité souhaitée :", min_value=1, value=1, step=1)
            
            if "panier" not in st.session_state:
                st.session_state.panier = []
                
            if st.button("➕ Ajouter au panier"):
                art_details = options_articles[art_choisi_nom]
                st.session_state.panier.append({
                    "designation": art_details["designation"],
                    "categorie": art_details["categorie"],
                    "cdt": art_details["cdt"],
                    "ref_fab": art_details["ref_fab"],
                    "quantite": int(quantite_demandee)
                })
                st.success(f"Ajouté : {quantite_demandee}x {art_choisi_nom}")
                st.rerun()
                
            # Affichage du panier actuel
            if st.session_state.panier:
                st.write("---")
                st.subheader("🛒 Votre Panier de Demande")
                df_panier = pd.DataFrame(st.session_state.panier)
                st.dataframe(df_panier, use_container_width=True)
                
                col_pan1, col_pan2 = st.columns(2)
                with col_pan1:
                    if st.button("🚀 Soumettre la demande à Olivier", type="primary", use_container_width=True):
                        if nom_demande and equipe_demande:
                            st.session_state.commandes_attente.append({
                                "id": len(st.session_state.commandes_attente) + 1,
                                "chercheur": nom_demande,
                                "equipe": equipe_demande,
                                "date": datetime.today().strftime("%d/%m/%Y à %H:%M"),
                                "items": st.session_state.panier.copy(),
                                "statut": "En attente"
                            })
                            st.session_state.panier = []
                            st.balloons()
                            st.success("✅ Votre demande a bien été transmise à Olivier ! Vous pouvez aller récupérer vos consommables.")
                            st.rerun()
                        else:
                            st.error("⚠️ Veuillez renseigner votre Nom et votre Équipe avant de valider.")
                with col_pan2:
                    if st.button("🗑️ Vider le panier", use_container_width=True):
                        st.session_state.panier = []
                        st.rerun()
                        
        with tab_cat:
            st.subheader("📋 État général de l'inventaire")
            df_public = pd.DataFrame(st.session_state.db_stock)
            df_public_display = df_public[["categorie", "designation", "cdt", "ref_fab", "stock"]].copy()
            df_public_display.columns = ["Catégorie", "Désignation", "Conditionnement", "Réf Fabricant", "En Stock"]
            st.dataframe(df_public_display, use_container_width=True)

# ──────────────────────────────────────────────────────────────
# ONGLET 2 : ESPACE D'ADMINISTRATION (OLIVIER)
# ──────────────────────────────────────────────────────────────
elif onglet == "🔑 Espace Administration (Olivier)":
    st.header("🔑 Espace Gestionnaire de Stock")
    
    password = st.text_input("Code de sécurité administrateur :", type="password")
    
    if password == CONFIG["admin_pass"]:
        st.success("🔓 Accès administrateur autorisé.")
        
        adm_tab1, adm_tab2, adm_tab3 = st.tabs([
            "📥 File d'attente des commandes", 
            "✏️ Éditeur de Stock Interactif (Type Excel)", 
            "🔄 Synchronisation & Réinitialisation"
        ])
        
        # ─── SOUS-ONGLET 1 : COMMANDES REÇUES À PRÉPARER ───
        with adm_tab1:
            st.subheader("📦 Commandes à distribuer")
            attente = [c for c in st.session_state.commandes_attente if c["statut"] == "En attente"]
            
            if not attente:
                st.info("☕ Aucune commande en attente pour le moment.")
            else:
                for cmd in attente:
                    with st.expander(f"📋 Commande #{cmd['id']} - {cmd['chercheur']} ({cmd['equipe']}) - {cmd['date']}"):
                        df_items_cmd = pd.DataFrame(cmd["items"])
                        st.dataframe(df_items_cmd[["designation", "cdt", "ref_fab", "quantite"]], use_container_width=True)
                        
                        col_cmd1, col_cmd2 = st.columns(2)
                        with col_cmd1:
                            if st.button("✅ Valider & déduire du stock physique", key=f"val_{cmd['id']}", use_container_width=True):
                                # Appliquer la déduction
                                error_flag = False
                                for req_item in cmd["items"]:
                                    match = next((item for item in st.session_state.db_stock if item["designation"] == req_item["designation"]), None)
                                    if match:
                                        if match["stock"] < req_item["quantite"]:
                                            st.error(f"Stock insuffisant pour {req_item['designation']} (Requis: {req_item['quantite']}, En stock: {match['stock']})")
                                            error_flag = True
                                
                                if not error_flag:
                                    for req_item in cmd["items"]:
                                        match = next((item for item in st.session_state.db_stock if item["designation"] == req_item["designation"]), None)
                                        if match:
                                            match["stock"] -= req_item["quantite"]
                                    cmd["statut"] = "Délivrée"
                                    save_state_to_file()
                                    st.success("✅ Stock déduit et commande archivée !")
                                    st.rerun()
                        with col_cmd2:
                            if st.button("❌ Rejeter / Annuler", key=f"rej_{cmd['id']}", use_container_width=True):
                                cmd["statut"] = "Annulée"
                                st.warning("Commande annulée.")
                                st.rerun()

        # ─── SOUS-ONGLET 2 : EDITEUR DIRECT DU STOCK (TYPE EXCEL) ───
        with adm_tab2:
            st.subheader("✏️ Édition instantanée de vos données")
            st.write("Double-cliquez sur n'importe quelle case ci-dessous pour modifier directement le stock, le nom, la catégorie ou la référence. Vous pouvez également cliquer sur la ligne vide du bas pour ajouter manuellement un article.")
            
            # Conversion de la base de données en DataFrame
            df_editor = pd.DataFrame(st.session_state.db_stock)
            if df_editor.empty:
                df_editor = pd.DataFrame(columns=["categorie", "designation", "cdt", "ref_fab", "stock", "seuil_alerte"])
                
            # Clé unique dynamique pour éviter que Streamlit ne réinitialise les modifications 
            # à chaque rechargement provoqué par le clic sur le bouton de sauvegarde
            editor_key = f"stock_editor_v{st.session_state.editor_version}"
            
            # Configuration du tableau interactif éditable
            edited_df = st.data_editor(
                df_editor,
                column_config={
                    "categorie": st.column_config.SelectboxColumn("Catégorie", options=OFFICIAL_CATEGORIES, width="medium"),
                    "designation": st.column_config.TextColumn("Désignation Produit", required=True, width="large"),
                    "cdt": st.column_config.TextColumn("Conditionnement", width="medium"),
                    "ref_fab": st.column_config.TextColumn("Réf Fabricant", width="medium"),
                    "stock": st.column_config.NumberColumn("Quantité en Stock", min_value=0, required=True),
                    "seuil_alerte": st.column_config.NumberColumn("Seuil Alerte", min_value=0, required=True),
                },
                num_rows="dynamic", # Permet d'ajouter ou supprimer des lignes librement !
                use_container_width=True,
                key=editor_key
            )
            
            # Sauvegarde manuelle des données éditées
            if st.button("💾 Enregistrer toutes les modifications du tableau", type="primary", use_container_width=True):
                # Récupération fine de l'état actuel brut de l'éditeur en session
                if editor_key in st.session_state:
                    state_changes = st.session_state[editor_key]
                    final_df = apply_editor_changes(df_editor, state_changes)
                else:
                    final_df = edited_df
                
                # Sauvegarde finale en mémoire et sur fichier JSON
                st.session_state.db_stock = final_df.to_dict(orient="records")
                save_state_to_file()
                
                # Incrémente la version pour détruire l'ancien cache de composants Streamlit
                st.session_state.editor_version += 1
                
                st.success("✅ Base de données mise à jour et sauvegardée avec succès !")
                st.rerun()

        # ─── SOUS-ONGLET 3 : PARSING EXCEL & REINITIALISATION ───
        with adm_tab3:
            st.subheader("🔄 Synchronisation avec le fichier Excel INMED")
            st.write(f"Cette fonction va lire le fichier **`{EXCEL_FILE}`** à la racine de votre projet GitHub, en reconstruisant intelligemment les sections et les désignations.")
            
            if st.button("⚙️ Lancer la lecture automatique de l'Excel", use_container_width=True):
                if not Path(EXCEL_FILE).exists():
                    st.error(f"❌ Fichier `{EXCEL_FILE}` introuvable à la racine de votre répertoire. Assurez-vous qu'il est bien présent sur GitHub.")
                else:
                    with st.status("Lecture et analyse fine de votre Excel en cours...", expanded=True) as status:
                        res = import_excel_catalog(EXCEL_FILE)
                        if res["success"]:
                            st.session_state.db_stock = res["data"]
                            save_state_to_file()
                            # Réinitialisation du composant de tableur
                            st.session_state.editor_version += 1
                            status.update(label="✅ Fichier lu et analysé à 100% sans erreur !", state="complete")
                            st.success(f"Bravo ! {len(res['data'])} articles ont été correctement extraits et importés dans votre inventaire.")
                            st.rerun()
                        else:
                            status.update(label="❌ Erreur durant la lecture", state="error")
                            st.error(res["error"])
                            
            st.write("---")
            st.subheader("⚠️ Réinitialisation complète")
            if st.button("🗑️ Effacer tout l'inventaire en cours", type="secondary", use_container_width=True):
                st.session_state.db_stock = []
                save_state_to_file()
                # Réinitialisation du composant de tableur
                st.session_state.editor_version += 1
                st.warning("Tout l'inventaire a été remis à zéro.")
                st.rerun()
                
    elif password != "":
        st.error("🔑 Code d'accès administrateur incorrect.")
