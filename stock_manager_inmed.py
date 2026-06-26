# ... existing code ...
@st.cache_data(ttl=60)
def load_data(reload_trigger):
    try:
        url = st.secrets.get("SHEET_URL")
        if not url: return "URL non configurée dans les secrets."
        df = pd.read_csv(url)
        # --- CORRECTION ROBUSTE ---
        # On supprime les espaces inutiles autour des noms et on uniformise
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return str(e)
# ... existing code ...
    with tab_cmd:
        cat_select = st.selectbox("1. Choisir une catégorie :", cats)
        filtered_df = data if cat_select == "Toutes" else data[data['Catégorie'] == cat_select]
        selected_idx = st.selectbox("3. Choisir un article :", options=filtered_df.index, format_func=lambda i: filtered_df.loc[i, 'Désignation'])
        item = data.loc[selected_idx]
        
        # --- CORRECTION ROBUSTE POUR INFORMATIONS ---
        # On cherche la colonne Informations (insensible à la casse ou espaces)
        cols = {c.lower(): c for c in item.index}
        info_col = cols.get("informations", None)
        
        info_texte = item[info_col] if info_col and pd.notna(item[info_col]) else "Aucune information complémentaire."
        
        # On fait pareil pour le conditionnement et la référence
        cdt_col = cols.get("conditionnement", None)
        cdt_texte = item[cdt_col] if cdt_col and pd.notna(item[cdt_col]) else "N/A"
        
        ref_col = cols.get("ref fabricant", "ref_fab") # Fallback si nom différent
        ref_texte = item[ref_col] if ref_col in item and pd.notna(item[ref_col]) else "N/A"
        
        st.info(f"**Info :** {info_texte} \n *Cdt : {cdt_texte}* | *Réf : {ref_texte}*")
# ... existing code ...
