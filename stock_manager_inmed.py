import streamlit as st
import pandas as pd
import os

# --- Configuration de la page ---
st.set_page_config(page_title="Gestion Stock INMED", page_icon="🧪")

# --- Chargement des données ---
@st.cache_data(ttl=600)
def load_data():
    # Vérification que le secret est défini
    if "SHEET_URL" not in st.secrets:
        st.error("Erreur : La variable 'SHEET_URL' est manquante dans les secrets.")
        return None
    
    try:
        url = st.secrets["SHEET_URL"]
        # Lecture du CSV via l'URL
        data = pd.read_csv(url)
        return data
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
        return None

# Chargement principal
data = load_data()

# Titre
st.title("🧪 Demande plastique - INMED")

# Vérification si les données sont bien chargées avant de continuer
if data is not None:
    # --- Interface de commande ---
    st.header("Passer une commande")
    
    # Sécurisation de la création de la liste de catégories
    if 'Catégorie' in data.columns:
        cats = ["Toutes"] + sorted(data['Catégorie'].dropna().unique().tolist())
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
    else:
        st.error("La colonne 'Catégorie' est introuvable dans le fichier.")
        cat_select = "Toutes"

    # --- Onglet de Contrôle Qualité (Préparation) ---
    st.divider()
    st.subheader("📸 Contrôle Qualité (Beta)")
    uploaded_file = st.file_uploader("Prendre une photo du produit pour vérification", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Produit à analyser", use_container_width=True)
        if st.button("Analyser la qualité"):
            st.info("Module d'analyse par vision en cours de configuration...")
            # Ici, nous appellerons plus tard l'IA Vision (ex: Gemini)
else:
    st.warning("Veuillez configurer correctement l'accès à vos données.")
