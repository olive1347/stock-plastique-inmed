import streamlit as st
import pandas as pd

# On définit la fonction sans arguments complexes pour éviter les conflits
@st.cache_data(ttl=60)
def load_data():
    try:
        url = st.secrets.get("SHEET_URL")
        if not url: return "URL non configurée dans les secrets."
        df = pd.read_csv(url)
        # Nettoyage systématique des colonnes
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return str(e)

st.title("🧪 Gestionnaire de Stock INMED")

# Chargement des données
data = load_data()

if isinstance(data, str):
    st.error(f"Erreur de chargement : {data}")
else:
    # Nettoyage des noms de colonnes pour la recherche (minuscules)
    data.columns = [c.strip().lower() for c in data.columns]
    
    # Vérification des colonnes nécessaires
    if 'catégorie' not in data.columns or 'désignation' not in data.columns:
        st.error(f"Colonnes manquantes dans le CSV. Colonnes trouvées : {list(data.columns)}")
    else:
        # Interface de sélection
        cats = ["Toutes"] + sorted([str(c) for c in data['catégorie'].dropna().unique()])
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        
        filtered_df = data if cat_select == "Toutes" else data[data['catégorie'] == cat_select]
        
        # Sélection d'article
        selected_idx = st.selectbox(
            "2. Choisir un article :", 
            options=filtered_df.index, 
            format_func=lambda i: filtered_df.loc[i, 'désignation']
        )
        item = data.loc[selected_idx]
        
        # Extraction sécurisée des informations
        info_texte = item.get('informations', "Aucune information complémentaire.")
        cdt_texte = item.get('conditionnement', "N/A")
        ref_texte = item.get('ref fabricant', "N/A")
        
        # Affichage propre
        st.info(f"**Info :** {info_texte} \n\n *Cdt : {cdt_texte}* | *Réf : {ref_texte}*")
        
        # Visualisation brute si besoin
        with st.expander("Voir tout le détail"):
            st.write(item)
