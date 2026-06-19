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
    official_cats = {
        "FILTRATION": ["filtration"],
        "HISTO ET ELECTROPHY": ["histo", "electrophy"],
        "TUBES": ["tubes"],
        "CULTURE CELLULAIRE": ["culture", "cellulaire"],
        "POINTES OU TIPS": ["pointe", "tip"],
        "SERINGUES ET AIGUILLES": ["seringue", "aiguille"],
        "BACTÉRIO": ["bacterio"],
        "PCR": ["pcr"],
        "DIVERS": ["divers"],
        "PESÉES": ["pesee", "pesees"]
    }
    for cat_name, keywords in official_cats.items():
        if any(k in clean_des for k in keywords):
            return cat_name
    return None

def get_cell_value(ws, row, col):
    cell = ws.cell(row=row, column=col)
    for merged_range in ws.merged_cells.ranges:
        if cell.coordinate in merged_range:
            return ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
    return cell.value

# --- INITIALISATION ---
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

if "db_stock" not in st.session_state:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st.session_state.db_stock = json.load(f)
    else:
        st.session_state.db_stock = []

st.title("🧪 GestStock INMED")

# --- NAVIGATION ---
tabs = st.tabs(["📋 Stock Actuel", "📦 Faire une demande", "⚙️ Administration"])

# ONGLET 1: STOCK
with tabs[0]:
    st.write("### Inventaire disponible")
    if not st.session_state.db_stock:
        st.warning("Aucune donnée. Allez dans l'onglet Administration pour synchroniser.")
    else:
        st.dataframe(st.session_state.db_stock)

# ONGLET 2: DEMANDES
with tabs[1]:
    st.write("### Faire une demande")
    st.write("Sélectionnez les articles depuis l'inventaire pour générer votre bon.")

# ONGLET 3: ADMINISTRATION
with tabs[2]:
    st.write("### Espace Administration")
    if st.button("⚙️ Lancer la synchronisation Excel", use_container_width=True):
        if not Path(EXCEL_FILE).exists():
            st.error(f"Fichier {EXCEL_FILE} introuvable.")
        else:
            with st.status("Synchronisation en cours...", expanded=True) as status:
                try:
                    wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
                    ws = wb.active
                    new_catalog = []
                    current_cat = "DIVERS"
                    
                    for r in range(5, ws.max_row + 1):
                        des = get_cell_value(ws, r, 1) # Col A
                        if not des: continue
                        cdt = get_cell_value(ws, r, 3) # Col C (Cdt)
                        ref = get_cell_value(ws, r, 5) # Col E (Ref)
                        
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
                    st.error(f"Erreur : {e}")
