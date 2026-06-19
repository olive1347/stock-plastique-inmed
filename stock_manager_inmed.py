import json
import re
import unicodedata
from pathlib import Path
import openpyxl
import streamlit as st
import pandas as pd

STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

# --- FONCTIONS UTILITAIRES ---
def save_db():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.db_stock, f, ensure_ascii=False, indent=4)

def load_db():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# --- INITIALISATION ---
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

if "db_stock" not in st.session_state:
    st.session_state.db_stock = load_db()

st.title("🧪 GestStock INMED")

# --- NAVIGATION ---
tabs = st.tabs(["📋 Stock Actuel", "📦 Faire une demande", "⚙️ Administration"])

# ONGLET 1: STOCK
with tabs[0]:
    st.write("### Inventaire disponible")
    if not st.session_state.db_stock:
        st.info("Aucun article en stock. Utilisez l'onglet Administration pour en ajouter.")
    else:
        df = pd.DataFrame(st.session_state.db_stock)
        st.dataframe(df, use_container_width=True)

# ONGLET 2: DEMANDES
with tabs[1]:
    st.write("### Faire une demande")
    if not st.session_state.db_stock:
        st.warning("Veuillez remplir le stock dans l'onglet Administration.")
    else:
        st.write("Sélectionnez les articles depuis l'inventaire pour générer votre bon.")
        # Exemple de sélection simple
        articles = [item['designation'] for item in st.session_state.db_stock]
        selection = st.multiselect("Articles à commander", articles)
        if selection:
            st.write("Vous avez sélectionné :", selection)
            if st.button("Valider la commande"):
                st.success("Commande envoyée !")

# ONGLET 3: ADMINISTRATION
with tabs[2]:
    st.write("### Espace Administration")
    
    # 1. Synchronisation Excel
    if st.button("⚙️ Lancer la synchronisation Excel", use_container_width=True):
        if not Path(EXCEL_FILE).exists():
            st.error(f"Fichier {EXCEL_FILE} introuvable.")
        else:
            try:
                wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
                ws = wb.active
                new_catalog = []
                current_cat = "DIVERS"
                
                for r in range(5, ws.max_row + 1):
                    des = ws.cell(row=r, column=1).value
                    if not des: continue
                    cdt = ws.cell(row=r, column=3).value
                    ref = ws.cell(row=r, column=5).value
                    
                    # Logique simple de détection de catégorie
                    if not cdt and not ref:
                        current_cat = str(des).upper()
                        continue
                    
                    new_catalog.append({
                        "categorie": current_cat,
                        "designation": str(des).strip(),
                        "cdt": str(cdt).strip() if cdt else "Unité",
                        "ref_fab": str(ref).strip() if ref else "N/A"
                    })
                
                st.session_state.db_stock = new_catalog
                save_db()
                st.success("Synchronisation terminée !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la lecture : {e}")

    st.write("---")
    
    # 2. Ajout manuel
    st.write("### Ajouter un article manuellement")
    with st.form("add_item_form"):
        col1, col2 = st.columns(2)
        designation = col1.text_input("Désignation")
        categorie = col2.selectbox("Catégorie", ["FILTRATION", "HISTO ET ELECTROPHY", "TUBES", "CULTURE CELLULAIRE", "POINTES OU TIPS", "SERINGUES ET AIGUILLES", "BACTÉRIO", "PCR", "DIVERS", "PESÉES"])
        cdt = col1.text_input("Conditionnement")
        ref_fab = col2.text_input("Référence Fabricant")
        
        submitted = st.form_submit_button("Ajouter l'article")
        if submitted and designation:
            st.session_state.db_stock.append({
                "categorie": categorie,
                "designation": designation,
                "cdt": cdt,
                "ref_fab": ref_fab
            })
            save_db()
            st.success(f"Article '{designation}' ajouté !")
            st.rerun()
            
    # 3. Supprimer tout
    if st.button("🗑️ Vider tout l'inventaire", type="primary"):
        st.session_state.db_stock = []
        save_db()
        st.rerun()
