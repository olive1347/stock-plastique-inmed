import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
if "page_configured" not in st.session_state:
    st.set_page_config(page_title="GestStock INMED", page_icon="🧪", layout="wide")
    st.session_state.page_configured = True

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .designation { font-weight: bold; color: #1e293b; font-size: 1.1em; }
    .info { color: #64748b; font-size: 0.9em; }
    </style>
""", unsafe_allow_html=True)

# --- DONNÉES ---
@st.cache_data
def load_data():
    df = pd.read_excel("stock-plastique.xlsx", sheet_name=0)
    
    # Correction des NaN : on propage la valeur du haut vers le bas
    if "Catégories" in df.columns:
        df["Catégories"] = df["Catégories"].ffill()
        
    # Optionnel : On peut aussi supprimer les lignes où la désignation est vide 
    # pour nettoyer l'affichage des lignes de séparation vides
    df = df.dropna(subset=['Designation'])
    
    return df

# --- HEADER ---
st.title("🧪 GestStock INMED")
st.subheader("Catalogue de consommables")

# --- RECHERCHE ---
col_s1, col_s2 = st.columns([1, 3])
with col_s1:
    search = st.text_input("🔍 Rechercher un article...")

# --- AFFICHAGE PAR CATÉGORIES ---
if not df.empty:
    categories = df["Catégories"].unique()
    
    for cat in categories:
        # Filtrage
        articles_cat = df[df["Catégories"] == cat]
        if search:
            articles_cat = articles_cat[articles_cat["Designation"].str.contains(search, case=False, na=False)]
        
        if not articles_cat.empty:
            with st.expander(f"📂 {cat}", expanded=True):
                # Utilisation de colonnes pour une vue catalogue
                cols = st.columns(2)
                for idx, (_, row) in enumerate(articles_cat.iterrows()):
                    with cols[idx % 2]:
                        st.markdown(f"""
                        <div class="card">
                            <div class="designation">{row['Designation']}</div>
                            <div class="info">{row['Informations']} | {row['Fabricant']}</div>
                        </div>
                        """, unsafe_allow_html=True)

st.write("---")

# --- FORMULAIRE DE COMMANDE ---
st.header("📝 Nouvelle Commande")
with st.form("cmd_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        nom = st.text_input("Demandeur")
    with c2:
        art = st.selectbox("Article", df["Designation"].dropna().unique())
    with c3:
        qte = st.number_input("Quantité", min_value=1, value=1)
    
    if st.form_submit_button("🚀 Envoyer la commande"):
        if nom:
            st.success(f"Commande de {qte} x {art} enregistrée pour {nom}.")
        else:
            st.warning("Veuillez indiquer votre nom.")
