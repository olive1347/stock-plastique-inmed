import streamlit as st
import pandas as pd

# --- CONFIGURATION INITIALE ---
if "page_configured" not in st.session_state:
    st.set_page_config(
        page_title="GestStock INMED", 
        page_icon="🧪", 
        layout="wide"
    )
    st.session_state.page_configured = True

# --- STYLE CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- EN-TÊTE ---
st.title("🧪 GestStock INMED")
st.markdown("### Sélection rapide de vos consommables")

# --- CHARGEMENT DES DONNÉES (XLSX) ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("stock-plastique.xlsx", sheet_name=0)
        if "Catégories" in df.columns:
            df["Catégories"] = df["Catégories"].ffill()
        return df
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- INTERFACE EN LISTE ---
    st.sidebar.header("🔍 Recherche")
    search = st.sidebar.text_input("Rechercher un article :")
    
    # Filtrage
    display_df = df.copy()
    if search:
        display_df = display_df[display_df["Designation"].str.contains(search, case=False, na=False)]

    # Affichage par catégories sous forme de liste déroulante (Expander)
    categories = display_df["Catégories"].unique()
    
    for cat in categories:
        with st.expander(f"📂 {cat}", expanded=False):
            # Liste des articles pour cette catégorie
            articles_cat = display_df[display_df["Catégories"] == cat]
            for _, row in articles_cat.iterrows():
                st.markdown(f"- **{row['Designation']}** | *{row['Informations']}*")

    st.write("---")

    # --- COMMANDE ---
    with st.expander("📝 Passer une commande express", expanded=True):
        with st.form("cmd_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                demandeur = st.text_input("Nom de l'utilisateur")
            with col2:
                article = st.selectbox("Article", df["Designation"].dropna().unique())
            with col3:
                qty = st.number_input("Quantité", min_value=1, value=1)
            
            submit = st.form_submit_button("Envoyer la commande")
            if submit and demandeur:
                st.success(f"Bravo {demandeur} ! Commande de {qty} x {article} enregistrée.")
            elif submit:
                st.error("Veuillez renseigner votre nom.")

st.sidebar.markdown("---")
st.sidebar.info("Responsable stock : Olivier Lassalle")
