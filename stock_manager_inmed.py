"""
GestStock INMED — Gestion du Stock Plastique & Consommables
Version corrigée avec retour visuel de synchronisation
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

# --- CONFIGURATION ---
try:
    groq_key = st.secrets.get("GROQ_API_KEY", st.secrets.get("groq_api_key", ""))
except Exception:
    groq_key = ""

CONFIG = {
    "groq_api_key": groq_key,
    "groq_url"    : "https://api.groq.com/openai/v1/chat/completions",
    "model"       : "llama-3.1-8b-instant",
    "admin_pass"  : "inmed2026",
}

STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

# --- FONCTIONS UTILITAIRES ---

def clean_text(text):
    """Nettoie une chaîne pour une comparaison robuste"""
    if not text: return ""
    s = str(text).lower()
    s = "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z]', '', s)

def identify_category(des_str, cdt, ref):
    """Identifie si une ligne est une catégorie officielle"""
    # Une catégorie n'a ni conditionnement ni référence
    if cdt or ref: return None
    
    clean_des = clean_text(des_str)
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

def detect_columns(ws):
    """Repère automatiquement les colonnes"""
    col_map = {"des": 1, "cdt": 2, "ref": 3, "qty": 8}
    for r in range(1, 11):
        for c in range(1, 15):
            val = str(ws.cell(row=r, column=c).value).upper()
            if "DESIGNATION" in val or "ARTICLE" in val: col_map["des"] = c
            if "CDT" in val or "DETAIL" in val: col_map["cdt"] = c
            if "REF" in val or "CODE" in val: col_map["ref"] = c
            if "QTY" in val or "QUANTITE" in val: col_map["qty"] = c
    return col_map["des"], col_map["cdt"], col_map["ref"], col_map["qty"]

def save_stock_state(db_stock):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(db_stock, f, ensure_ascii=False, indent=4)

# --- APP STREAMLIT ---
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

if "db_stock" not in st.session_state:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st.session_state.db_stock = json.load(f)
    else:
        st.session_state.db_stock = []

# ... (reste du code identique, voici la correction pour le bouton de sync) ...

# Remplacez le bloc du 3ème onglet dans votre code précédent par celui-ci :

# --- DANS L'ESPACE OLIVIER / ADMIN_TAB3 ---
# ...
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
                            col_des, col_cdt, col_ref, _ = detect_columns(ws)
                            
                            st.write("Analyse des lignes...")
                            new_catalog = []
                            current_cat = "DIVERS"
                            
                            for r in range(5, ws.max_row + 1):
                                des = get_cell_value(ws, r, col_des)
                                if not des: continue
                                
                                cdt = get_cell_value(ws, r, col_cdt)
                                ref = get_cell_value(ws, r, col_ref)
                                
                                # Détection catégorie
                                cat = identify_category(des, cdt, ref)
                                if cat:
                                    current_cat = cat
                                    continue
                                
                                # C'est un produit
                                new_catalog.append({
                                    "categorie": current_cat,
                                    "designation": str(des).strip(),
                                    "cdt": str(cdt).strip() if cdt else "Unité",
                                    "ref_fab": str(ref).strip() if ref else "N/A",
                                    "stock": 50, "seuil_alerte": 5
                                })
                            
                            st.session_state.db_stock = new_catalog
                            save_stock_state(new_catalog)
                            status.update(label="Synchronisation terminée !", state="complete")
                            st.rerun()
                        except Exception as e:
                            status.update(label="Erreur lors de la synchronisation", state="error")
                            st.error(f"Détails : {e}")
