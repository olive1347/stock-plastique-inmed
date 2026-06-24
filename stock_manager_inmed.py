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
st.markdown("### Gestion intuitive de vos consommables plastiques")

# --- CHARGEMENT DES DONNÉES (XLSX) ---
@st.cache_data
def load_data():
    try:
        # Lecture directe du fichier Excel
        # On suppose que les données sont dans la première feuille (index 0)
        df = pd.read_excel("stock-plastique.xlsx", sheet_name=0)
        
        # Nettoyage : Remplissage des cellules fusionnées dans la colonne Catégories
        if "Catégories" in df.columns:
            df["Catégories"] = df["Catégories"].ffill()
        return df
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier Excel : {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("Impossible de charger les données. Vérifiez que 'stock-plastique.xlsx' est bien à la racine du dépôt GitHub.")
else:
    # --- SIDEBAR FILTRES ---
    st.sidebar.header("🔍 Recherche & Filtres")
    categories = ["Toutes"] + list(df["Catégories"].dropna().unique())
    selected_cat = st.sidebar.selectbox("Filtrer par famille :", categories)
    search = st.sidebar.text_input("Rechercher un article :")

    # Application des filtres
    filtered_df = df.copy()
    if selected_cat != "Toutes":
        filtered_df = filtered_df[filtered_df["Catégories"] == selected_cat]
    if search:
        filtered_df = filtered_df[filtered_df["Designation"].str.contains(search, case=False, na=False)]

    # --- AFFICHAGE TABLEAU ---
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Prix": st.column_config.NumberColumn(format="%.2f €"),
        }
    )

    # --- COMMANDE ---
    with st.expander("📝 Passer une commande express", expanded=True):
        with st.form("cmd_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                demandeur = st.text_input("Nom de l'utilisateur")
            with col2:
                article = st.selectbox("Article", filtered_df["Designation"].unique())
            with col3:
                qty = st.number_input("Quantité", min_value=1, value=1)
            
            submit = st.form_submit_button("Envoyer la commande")
            if submit:
                if demandeur:
                    st.success(f"Bravo {demandeur} ! Commande de {qty} x {article} enregistrée.")
                else:
                    st.error("Veuillez renseigner votre nom.")

st.sidebar.markdown("---")
st.sidebar.info("Responsable stock : Olivier Lassalle")
