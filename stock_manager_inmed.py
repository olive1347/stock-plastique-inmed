import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
import openpyxl

# --- CONFIGURATION ---
STATE_FILE = "stock_state.json"
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

# --- FONCTIONS DE GESTION ---
def load_db():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_db(db):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

# --- INITIALISATION ---
st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

if "db_stock" not in st.session_state:
    st.session_state.db_stock = load_db()

st.title("🧪 GestStock INMED - Gestion des consommables")

# --- NAVIGATION ---
tabs = st.tabs(["📋 Stock Actuel", "📦 Faire une demande", "⚙️ Administration"])

# ONGLET 1: STOCK
with tabs[0]:
    st.header("Inventaire Disponible")
    if not st.session_state.db_stock:
        st.info("Aucun article en stock. Utilisez l'onglet Administration pour en ajouter.")
    else:
        df = pd.DataFrame(st.session_state.db_stock)
        st.dataframe(df, use_container_width=True)

# ONGLET 2: DEMANDES
with tabs[1]:
    st.header("Faire une demande")
    st.write("Sélectionnez les articles depuis l'inventaire.")
    if not st.session_state.db_stock:
        st.warning("Veuillez remplir le stock dans l'onglet Administration.")
    else:
        # Simple interface de sélection
        options = [f"{item['designation']} ({item['categorie']})" for item in st.session_state.db_stock]
        selection = st.multiselect("Articles à commander", options)
        if selection:
            st.write("Vous avez sélectionné :", selection)
            if st.button("Valider la commande"):
                st.success("Commande envoyée à Olivier !")

# ONGLET 3: ADMINISTRATION
with tabs[2]:
    st.header("Espace Administration")
    
    # 1. Ajout Manuel (FIXED)
    st.subheader("➕ Ajouter un article manuellement")
    with st.form("add_item_form"):
        col1, col2 = st.columns(2)
        designation = col1.text_input("Désignation")
        categorie = col2.selectbox("Catégorie", ["FILTRATION", "HISTO ET ELECTROPHY", "TUBES", "CULTURE CELLULAIRE", "POINTES OU TIPS", "SERINGUES ET AIGUILLES", "BACTÉRIO", "PCR", "DIVERS", "PESÉES"])
        cdt = col1.text_input("Conditionnement")
        ref_fab = col2.text_input("Référence Fabricant")
        
        submitted = st.form_submit_button("Ajouter l'article")
        if submitted:
            if designation:
                new_item = {
                    "categorie": categorie,
                    "designation": designation,
                    "cdt": cdt,
                    "ref_fab": ref_fab
                }
                st.session_state.db_stock.append(new_item)
                save_db(st.session_state.db_stock)
                st.success(f"Article '{designation}' ajouté !")
                st.rerun() # Rafraîchir pour voir l'ajout
            else:
                st.error("La désignation est obligatoire.")
    
    st.write("---")
    
    # 2. Synchronisation Excel (Optionnelle)
    st.subheader("⚙️ Synchronisation Excel")
    if st.button("Lancer la synchronisation Excel"):
        if not Path(EXCEL_FILE).exists():
            st.error(f"Fichier {EXCEL_FILE} introuvable dans le dossier.")
        else:
            try:
                wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
                ws = wb.active
                for r in range(5, ws.max_row + 1):
                    des = ws.cell(row=r, column=1).value
                    if not des: continue
                    # Logique simplifiée
                    st.session_state.db_stock.append({
                        "categorie": "Synchronisé",
                        "designation": str(des),
                        "cdt": str(ws.cell(row=r, column=3).value or ""),
                        "ref_fab": str(ws.cell(row=r, column=5).value or "")
                    })
                save_db(st.session_state.db_stock)
                st.success("Synchronisation terminée !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur de lecture : {e}")

    # 3. Vider tout
    if st.button("🗑️ Vider tout l'inventaire", type="primary"):
        st.session_state.db_stock = []
        save_db([])
        st.rerun()
