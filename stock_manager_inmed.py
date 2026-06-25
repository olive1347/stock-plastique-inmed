import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
if "page_configured" not in st.session_state:
    st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="centered")
    st.session_state.page_configured = True

# --- DONNÉES ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("stock-plastique.xlsx", sheet_name=0)
        # Nettoyage robuste des données
        if "Catégories" in df.columns:
            df["Catégories"] = df["Catégories"].ffill()
        # Suppression des lignes vides inutiles
        df = df.dropna(subset=['Designation'])
        return df
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")
        return pd.DataFrame()

df = load_data()

# --- HEADER ---
st.title("🧪 GestStock INMED")
st.subheader("Sélectionnez vos consommables")

if not df.empty:
    # 1. Sélection de la catégorie
    categories = df["Catégories"].unique()
    selected_cat = st.selectbox("📂 Choisissez une catégorie :", categories)

    # 2. Filtrage des articles selon la catégorie
    articles_in_cat = df[df["Catégories"] == selected_cat]
    
    # 3. Sélection de l'article
    # On crée une liste de tuples pour afficher "Désignation - Informations"
    article_options = articles_in_cat["Designation"].tolist()
    selected_art = st.selectbox("🧪 Choisissez l'article :", article_options)

    # Récupération des infos de l'article sélectionné
    article_info = articles_in_cat[articles_in_cat["Designation"] == selected_art].iloc[0]
    
    # Affichage des détails techniques
    st.info(f"**Détails :** {article_info['Informations']} | **Fabricant :** {article_info['Fabricant']}")

    st.write("---")

    # --- FORMULAIRE DE COMMANDE ---
    st.header("📝 Nouvelle Commande")
    with st.form("cmd_form"):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            nom = st.text_input("Demandeur")
        with col_c2:
            qte = st.number_input("Quantité", min_value=1, value=1)
        
        if st.form_submit_button("🚀 Envoyer la commande"):
            if nom:
                st.success(f"Commande de {qte} x {selected_art} enregistrée pour {nom}.")
            else:
                st.warning("Veuillez indiquer votre nom.")
else:
    st.error("Aucune donnée trouvée dans le fichier Excel.")
