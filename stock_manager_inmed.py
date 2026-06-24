import streamlit as st
import pandas as pd

# Configuration de la page pour une expérience moderne
st.set_page_config(
    page_title="GestStock INMED", 
    page_icon="🧪", 
    layout="wide"
)

# Style CSS personnalisé pour une interface "qui fait envie"
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .css-1r6slbo { background-color: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    </style>
""", unsafe_allow_html=True)

# --- EN-TÊTE ---
st.title("🧪 GestStock INMED")
st.markdown("### Gestion intuitive de vos consommables plastiques")

# --- CHARGEMENT ---
@st.cache_data
def load_data():
    # Chargement du fichier
    df = pd.read_csv("stock-plastique.xlsx - Feuil1.csv")
    df["Catégories"] = df["Catégories"].ffill()
    return df

try:
    df = load_data()
    
    # Sidebar : Filtres élégants
    st.sidebar.header("🔍 Recherche & Filtres")
    categories = ["Toutes"] + list(df["Catégories"].dropna().unique())
    selected_cat = st.sidebar.selectbox("Filtrer par famille :", categories)
    search = st.sidebar.text_input("Rechercher un article :")

    # Application des filtres
    if selected_cat != "Toutes":
        df = df[df["Catégories"] == selected_cat]
    if search:
        df = df[df["Designation"].str.contains(search, case=False, na=False)]

    # --- AFFICHAGE TABLEAU ---
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Prix ": st.column_config.NumberColumn(format="%.2f €"),
        }
    )

    # --- COMMANDE ---
    with st.expander("📝 Passer une commande express", expanded=True):
        with st.form("cmd_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                demandeur = st.text_input("Nom de l'utilisateur")
            with col2:
                article = st.selectbox("Article", df["Designation"].unique())
            with col3:
                qty = st.number_input("Quantité", min_value=1, value=1)
            
            submit = st.form_submit_button("Envoyer la commande")
            if submit and demandeur:
                st.success(f"Bravo {demandeur} ! Commande de {qty} x {article} enregistrée.")

except Exception as e:
    st.error("Oups ! Le fichier de données semble inaccessible. Vérifiez sa présence.")

st.sidebar.markdown("---")
st.sidebar.info("Responsable stock : Olivier Lassalle")
