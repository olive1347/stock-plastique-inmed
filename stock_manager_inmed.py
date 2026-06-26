import streamlit as st
import pandas as pd
import numpy as np

@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        url = st.secrets.get("SHEET_URL")
        if not url: return "URL non configurée dans les secrets."
        df = pd.read_csv(url)
        # On supprime les espaces inutiles autour des noms de colonnes
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return str(e)

st.title("Gestionnaire de Stock INMED")
data = load_data(time=None) # Simplifié pour l'exemple

if isinstance(data, str):
    st.error(f"Erreur de chargement : {data}")
else:
    # Interface de sélection
    cats = ["Toutes"] + list(data['Catégorie'].unique())
    tab_cmd = st.container()
    
    with tab_cmd:
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
        
        # Sélection d'article
        selected_idx = st.selectbox("3. Choisir un article :", options=filtered_df.index, format_func=lambda i: filtered_df.loc[i, 'Désignation'])
        item = data.loc[selected_idx]
        
        # Correction robuste pour les colonnes
        cols = {c.lower(): c for c in item.index}
        info_col = cols.get("informations", None)
        info_texte = item[info_col] if info_col and pd.notna(item[info_col]) else "Aucune information complémentaire."
        
        cdt_col = cols.get("conditionnement", None)
        cdt_texte = item[cdt_col] if cdt_col and pd.notna(item[cdt_col]) else "N/A"
        
        ref_col = cols.get("ref fabricant", "ref_fab")
        ref_texte = item[ref_col] if ref_col in item and pd.notna(item[ref_col]) else "N/A"
        
        st.info(f"**Info :** {info_texte} \n *Cdt : {cdt_texte}* | *Réf : {ref_texte}*")
