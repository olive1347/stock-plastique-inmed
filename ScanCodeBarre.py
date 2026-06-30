import streamlit as st
import pandas as pd
import os

# Configuration de la page
st.set_page_config(page_title="Gestion Stock Labo", layout="wide")

FICHIER_DB = 'stock_labo.csv'

# Initialisation du fichier CSV
if not os.path.exists(FICHIER_DB):
    df_init = pd.DataFrame(columns=['CodeBarre', 'NomProduit', 'ReferenceFournisseur', 'Fournisseur'])
    df_init.to_csv(FICHIER_DB, index=False)

# Chargement des données
@st.cache_data(ttl=1)
def load_data():
    return pd.read_csv(FICHIER_DB)

df = load_data()

st.title("🧪 Gestionnaire d'Inventaire de Laboratoire")

# Sidebar pour le scan
st.sidebar.header("Scanner un produit")
code_scan = st.sidebar.text_input("Code-barres :", key="scanner_input")

if code_scan:
    # Recherche
    resultat = df[df['CodeBarre'].astype(str) == code_scan]
    
    if not resultat.empty:
        st.success("Produit trouvé !")
        st.write(resultat)
    else:
        st.warning("Produit inconnu.")
        with st.form("ajout_form"):
            st.write("Ajouter ce nouveau produit :")
            nom = st.text_input("Nom du produit")
            ref = st.text_input("Référence fournisseur")
            fourn = st.text_input("Nom du fournisseur")
            if st.form_submit_button("Enregistrer"):
                nouvelle_ligne = pd.DataFrame([[code_scan, nom, ref, fourn]], 
                                            columns=['CodeBarre', 'NomProduit', 'ReferenceFournisseur', 'Fournisseur'])
                df = pd.concat([df, nouvelle_ligne], ignore_index=True)
                df.to_csv(FICHIER_DB, index=False)
                st.rerun()

# Affichage de l'inventaire complet
st.divider()
st.subheader("Inventaire complet")
st.dataframe(df, use_container_width=True)

# Bouton de téléchargement
st.download_button("Télécharger l'inventaire (CSV)", data=df.to_csv(index=False), file_name="inventaire_labo.csv")
