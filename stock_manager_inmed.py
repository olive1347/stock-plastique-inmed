import streamlit as st
import pandas as pd
import os

# --- CONFIGURATION ---
DATA_FILE = "stock_inmed.csv"

st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")

# --- GESTION DES DONNÉES ---
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Nettoyage automatique des colonnes
        if 'Prix' in df.columns:
            df = df.drop(columns=['Prix'])
        if 'Conditionnement' not in df.columns:
            df['Conditionnement'] = ""
        # On s'assure qu'il n'y a pas de lignes vides gênantes
        df = df.dropna(subset=['Désignation'])
        return df
    else:
        # Création d'une structure vide par défaut
        return pd.DataFrame(columns=['Catégorie', 'Désignation', 'Informations', 'Conditionnement', 'Fabricant', 'Ref fabricant', 'Ref UGAP'])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- INTERFACE ---
st.title("🧪 GestStock INMED")

# Chargement des données
df = load_data()

# Onglets
tab_cmd, tab_gest = st.tabs(["🛒 Commander", "🛠️ Gestion Inventaire"])

# --- TAB 1 : COMMANDE ---
with tab_cmd:
    st.subheader("Passer une commande")
    if not df.empty:
        # Sélection catégorie
        cats = ["Toutes"] + df['Catégorie'].dropna().unique().tolist()
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        
        filtered_df = df if cat_select == "Toutes" else df[df['Catégorie'] == cat_select]
        
        # Sélection article avec le correctif pour les doublons
        st.write("2. Choisir un article :")
        selected_index = st.selectbox(
            "Article", 
            options=filtered_df.index, 
            format_func=lambda x: f"{filtered_df.loc[x, 'Désignation']} ({filtered_df.loc[x, 'Informations']})"
        )
        
        if selected_index is not None:
            item = df.loc[selected_index]
            st.info(f"**Article :** {item['Désignation']} | **Info :** {item['Informations']} | **Cond. :** {item['Conditionnement']} | **Fabricant :** {item['Fabricant']}")
            
            qty = st.number_input("Quantité", min_value=1, value=1)
            nom = st.text_input("Votre Nom")
            
            if st.button("🚀 Envoyer la commande"):
                if nom:
                    st.success(f"Commande de {qty} x {item['Désignation']} ({item['Informations']}) enregistrée !")
                else:
                    st.warning("Veuillez indiquer votre nom.")
    else:
        st.warning("L'inventaire est vide. Utilisez l'onglet 'Gestion Inventaire' pour ajouter vos produits.")

# --- TAB 2 : GESTION INVENTAIRE ---
with tab_gest:
    st.subheader("🛠️ Édition du Stock")
    st.write("Modifiez, ajoutez ou supprimez des articles ici. Cliquez sur 'Sauvegarder' pour appliquer.")
    
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
