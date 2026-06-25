import streamlit as st
import pandas as pd
import os

# --- CONFIGURATION ---
DATA_FILE = "stock_inmed.csv"

if "page_configured" not in st.session_state:
    st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
    st.session_state.page_configured = True

# --- GESTION DES DONNÉES ---
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        # Template de base si le fichier n'existe pas
        return pd.DataFrame(columns=['Catégorie', 'Désignation', 'Informations', 'Fabricant', 'Prix'])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- INTERFACE ---
st.title("🧪 GestStock INMED")

# Chargement
df = load_data()

# Onglets
tab_cmd, tab_gest = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire"])

# --- TAB 1 : COMMANDE ---
with tab_cmd:
    st.subheader("Passer une commande")
    if not df.empty:
        # Listes déroulantes pour simplifier
        cats = ["Toutes"] + df['Catégorie'].dropna().unique().tolist()
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        
        filtered_df = df if cat_select == "Toutes" else df[df['Catégorie'] == cat_select]
        
        designations = filtered_df['Désignation'].unique().tolist()
        art_select = st.selectbox("2. Choisir un article :", designations)
        
        # Détails auto
        if art_select:
            item = df[df['Désignation'] == art_select].iloc[0]
            st.info(f"**Info :** {item['Informations']} | **Fabricant :** {item['Fabricant']} | **Prix :** {item['Prix']}€")
            
            qty = st.number_input("Quantité", min_value=1, value=1)
            nom = st.text_input("Votre Nom")
            
            if st.button("🚀 Envoyer la commande"):
                if nom:
                    st.success(f"Commande de {qty} x {art_select} envoyée !")
                else:
                    st.warning("Indiquez votre nom svp.")
    else:
        st.warning("L'inventaire est vide. Passez par l'onglet 'Gestion Inventaire' pour ajouter des produits.")

# --- TAB 2 : GESTION INVENTAIRE (Admin) ---
with tab_gest:
    st.subheader("🛠️ Édition du Stock")
    st.write("Modifiez directement le tableau ci-dessous. Les changements sont enregistrés au clic sur le bouton.")
    
    # Éditeur interactif
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        key="editor"
    )
    
    if st.button("💾 Sauvegarder les modifications"):
        save_data(edited_df)
        st.success("Inventaire mis à jour avec succès !")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Responsable stock : Olivier Lassalle")
