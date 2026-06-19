"""
GestStock INMED — Gestion du Stock Plastique & Consommables
Version corrigée avec retour visuel de synchronisation
"""

import json
import re
import unicodedata
from pathlib import Path
import openpyxl
import streamlit as st

STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

# --- FONCTIONS UTILITAIRES ---
def clean_text(text):
    if not text: return ""
    s = str(text).lower()
    s = "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z]', '', s)

def identify_category(des_str, cdt, ref):
    if cdt or ref: return None
    clean_des = clean_text(des_str)
    # Liste officielle des catégories
    official_cats = {
        "filtration": ["filtration"],
        "histo et electrophy": ["histo", "electrophy"],
        "tubes": ["tubes"],
        "culture cellulaire": ["culture", "cellulaire"],
        "pointes ou tips": ["pointe", "tip"],
        "seringues et aiguilles": ["seringue", "aiguille"],
        "bactério": ["bacterio"],
        "pcr": ["pcr"],
        "divers": ["divers"],
        "pesées": ["pesee", "pesees"]
    }
    for cat_name, keywords in official_cats.items():
        if any(k in clean_des for k in keywords):
            return cat_name.upper()
    return None

def get_cell_value(ws, row, col):
    cell = ws.cell(row=row, column=col)
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
    return cell.value

st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

if "db_stock" not in st.session_state:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st.session_state.db_stock = json.load(f)
    else:
        st.session_state.db_stock = []

# --- INTERFACE ADMIN ---
# (Simulé ici pour la structure, assurez-vous de placer ceci dans votre logique d'onglet)
st.write("### Espace Administration")
st.write("**🔄 Synchroniser l'application avec l'Excel :**")

if st.button("⚙️ Lancer la synchronisation Excel", use_container_width=True):
    if not Path(EXCEL_FILE).exists():
        st.error(f"Fichier {EXCEL_FILE} introuvable sur le serveur.")
    else:
        with st.status("Synchronisation en cours...", expanded=True) as status:
            try:
                st.write("Chargement du fichier Excel...")
                wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
                ws = wb.active
                
                # Détection colonne (simplifiée)
                col_des, col_cdt, col_ref = 1, 2, 3
                
                st.write("Analyse des lignes...")
                new_catalog = []
                current_cat = "DIVERS"
                
                for r in range(5, ws.max_row + 1):
                    des = get_cell_value(ws, r, col_des)
                    if not des: continue
                    
                    cdt = get_cell_value(ws, r, col_cdt)
                    ref = get_cell_value(ws, r, col_ref)
                    
                    cat = identify_category(des, cdt, ref)
                    if cat:
                        current_cat = cat
                        continue
                    
                    new_catalog.append({
                        "categorie": current_cat,
                        "designation": str(des).strip(),
                        "cdt": str(cdt).strip() if cdt else "Unité",
                        "ref_fab": str(ref).strip() if ref else "N/A"
                    })
                
                st.session_state.db_stock = new_catalog
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_catalog, f, ensure_ascii=False, indent=4)
                
                status.update(label="Synchronisation terminée !", state="complete")
                st.rerun()
            except Exception as e:
                status.update(label="Erreur lors de la synchronisation", state="error")
                st.error(f"Détails : {e}")
