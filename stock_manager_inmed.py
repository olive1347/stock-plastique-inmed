import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==============================================================================
# CONFIGURATION DE LA PAGE (Doit impérativement être la première commande)
# ==============================================================================
st.set_page_config(
    page_title="INMED - Gestion du Stock de Plastique",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# CONSTANTES ET CONFIGURATION DES FICHIERS
# ==============================================================================
DB_FILE = "stock_plastique_inmed.xlsx"
DEFAULT_COLUMNS = ["id", "categorie", "designation", "reference", "quantite", "seuil_alerte", "localisation"]

# Données d'initialisation par défaut si le fichier Excel n'existe pas
DEFAULT_DATA = [
    {"id": 1, "categorie": "Tubes", "designation": "Eppendorf 1.5mL microcentrifuge", "reference": "EP-150", "quantite": 500, "seuil_alerte": 100, "localisation": "Armoire A1"},
    {"id": 2, "categorie": "Tubes", "designation": "Falcon 15mL conique sterile", "reference": "FA-15", "quantite": 250, "seuil_alerte": 50, "localisation": "Armoire A2"},
    {"id": 3, "categorie": "Tubes", "designation": "Falcon 50mL conique sterile", "reference": "FA-50", "quantite": 180, "seuil_alerte": 40, "localisation": "Armoire A2"},
    {"id": 4, "categorie": "Pipettes", "designation": "Pipette serologique 10mL", "reference": "PS-10", "quantite": 300, "seuil_alerte": 60, "localisation": "Étagère B1"},
    {"id": 5, "categorie": "Pipettes", "designation": "Pipette serologique 25mL", "reference": "PS-25", "quantite": 150, "seuil_alerte": 30, "localisation": "Étagère B1"},
    {"id": 6, "categorie": "Boites de Petri", "designation": "Boite de Petri 100mm ventilée", "reference": "BP-100", "quantite": 400, "seuil_alerte": 80, "localisation": "Armoire C1"},
    {"id": 7, "categorie": "Pointe Pipette", "designation": "Pointe Filter Tips 200uL", "reference": "PT-200F", "quantite": 600, "seuil_alerte": 150, "localisation": "Étagère C2"},
]

# ==============================================================================
# FONCTIONS UTILITAIRES / ACCÈS DONNÉES
# ==============================================================================

def get_user_ip():
    """Récupère l'adresse IP réelle du chercheur à partir des en-têtes HTTP de Streamlit"""
    try:
        # Tente de récupérer l'adresse IP via le contexte Streamlit récent
        headers = st.context.headers
        if "x-forwarded-for" in headers:
            return headers["x-forwarded-for"].split(",")[0].strip()
        if "x-real-ip" in headers:
            return headers["x-real-ip"]
    except Exception:
        pass
    return "IP Locale / Inconnue"


def init_database():
    """Initialise le fichier Excel de base s'il est manquant ou altéré"""
    if not os.path.exists(DB_FILE):
        try:
            with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
                # Onglet principal du stock
                df_stock = pd.DataFrame(DEFAULT_DATA)
                df_stock.to_excel(writer, sheet_name="Stock", index=False)
                # Onglet historique des transactions
                df_logs = pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])
                df_logs.to_excel(writer, sheet_name="Logs", index=False)
        except Exception as e:
            st.error(f"Impossible d'écrire le fichier d'initialisation Excel : {e}")


def load_data():
    """Charge la base de données Excel de manière sécurisée"""
    init_database()
    try:
        df_stock = pd.read_excel(DB_FILE, sheet_name="Stock")
        # Vérification et nettoyage des colonnes requises
        for col in DEFAULT_COLUMNS:
            if col not in df_stock.columns:
                df_stock[col] = "" if col != "quantite" and col != "seuil_alerte" else 0
        
        # S'assurer des types corrects
        df_stock["id"] = df_stock["id"].astype(int)
        df_stock["quantite"] = pd.to_numeric(df_stock["quantite"], errors="coerce").fillna(0).astype(int)
        df_stock["seuil_alerte"] = pd.to_numeric(df_stock["seuil_alerte"], errors="coerce").fillna(0).astype(int)
        
        # Chargement des logs
        try:
            df_logs = pd.read_excel(DB_FILE, sheet_name="Logs")
        except Exception:
            df_logs = pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])
            
        return df_stock, df_logs
    except Exception as e:
        st.error(f"Erreur lors du chargement des données Excel : {e}")
        # Fallback sécurisé en mémoire en cas de corruption de fichier
        return pd.DataFrame(DEFAULT_DATA), pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])


def save_data(df_stock, df_logs=None):
    """Enregistre le stock et les logs dans le fichier Excel"""
    try:
        # Si aucun log n'est fourni, on conserve les logs existants
        if df_logs is None:
            _, df_logs = load_data()
            
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            df_stock.to_excel(writer, sheet_name="Stock", index=False)
            df_logs.to_excel(writer, sheet_name="Logs", index=False)
        return True
    except Exception as e:
        st.error(f"Erreur d'écriture dans le fichier Excel : {e}")
        return False


def add_transaction_log(utilisateur, action, designation, quantite_mouvement, nouveau_stock):
    """Ajoute une ligne de log dans l'historique d'audit"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    heure_str = now.strftime("%H:%M:%S")
    ip_address = get_user_ip()
    
    new_log = {
        "date": date_str,
        "heure": heure_str,
        "ip": ip_address,
        "utilisateur": utilisateur if utilisateur else "Anonyme",
        "action": action,
        "designation": designation,
        "quantite_mouvement": quantite_mouvement,
        "nouveau_stock": nouveau_stock
    }
    
    # Ajout au DataFrame de session et écriture disque
    st.session_state.db_logs = pd.concat([st.session_state.db_logs, pd.DataFrame([new_log])], ignore_index=True)
    save_data(st.session_state.db_stock, st.session_state.db_logs)


# ==============================================================================
# GESTION DES ÉTATS DE SESSION
# ==============================================================================
if "db_stock" not in st.session_state or "db_logs" not in st.session_state:
    df_s, df_l = load_data()
    st.session_state.db_stock = df_s
    st.session_state.db_logs = df_l

# ==============================================================================
# EN-TÊTE GRAPHIQUE
# ==============================================================================
st.markdown(
    """
    <div style="background-color:#1E3A8A;padding:18px;border-radius:10px;margin-bottom:20px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:28px;">🔬 INMED - Gestionnaire de Consommables Plastiques</h1>
        <p style="color:#BFDBFE;margin:5px 0 0 0;font-size:14px;">Suivi en temps réel et traçabilité des consommables de laboratoire</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Récupération de l'IP actuelle pour l'afficher en bas ou dans la sidebar
current_user_ip = get_user_ip()

# ==============================================================================
# BARRE LATÉRALE - NAVIGATION ET INFOS
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/plasticine/100/test-tube.png", width=70)
    st.title("Menu de Navigation")
    
    page = st.radio(
        "Sélectionnez un espace :",
        ["🔬 Consultation et Retrait", "⚙️ Administration"]
    )
    
    st.divider()
    st.markdown("### 💻 Informations Connexion")
    st.caption(f"**Votre IP identifiée :** `{current_user_ip}`")
    st.caption("Application interne réservée aux membres de l'INMED.")

# ==============================================================================
# ESPACE 1 : CONSULTATION ET RETRAIT (POUR TOUS LES CHERCHEURS)
# ==============================================================================
if page == "🔬 Consultation et Retrait":
    st.header("📦 État du Stock & Prélèvement")
    
    # 1. Extraction robuste des catégories pour éviter les TypeErrors
    if isinstance(st.session_state.db_stock, pd.DataFrame):
        categories_existantes = sorted(list(st.session_state.db_stock["categorie"].dropna().unique()))
    else:
        # Fallback de secours si le format de session a été altéré
        categories_existantes = []
        
    # Filtres de recherche
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        recherche = st.text_input("🔍 Rechercher un consommable (Désignation, Référence...) :", "").strip()
    with col_f2:
        categorie_selectionnee = st.selectbox("📂 Filtrer par Catégorie :", ["Toutes"] + categories_existantes)
        
    # Filtrage dynamique du DataFrame
    df_filtre = st.session_state.db_stock.copy()
    if categorie_selectionnee != "Toutes":
        df_filtre = df_filtre[df_filtre["categorie"] == categorie_selectionnee]
    if recherche:
        df_filtre = df_filtre[
            df_filtre["designation"].str.contains(recherche, case=False, na=False) |
            df_filtre["reference"].str.contains(recherche, case=False, na=False)
        ]
        
    # Alerte de stock bas visuelle
    items_critiques = df_filtre[df_filtre["quantite"] <= df_filtre["seuil_alerte"]]
    if not items_critiques.empty:
        st.warning(f"⚠️ **Attention :** {len(items_critiques)} consommables ont atteint leur seuil d'alerte et doivent être réapprovisionnés !")
        
    # Affichage du tableau interactif
    st.markdown("### Liste du matériel disponible")
    
    # Styliser le tableau pour mettre en valeur les stocks bas
    def colorier_ligne(row):
        return ['background-color: #FEE2E2' if row['quantite'] <= row['seuil_alerte'] else '' for _ in row]
    
    df_style = df_filtre.style.apply(colorier_ligne, axis=1)
    
    st.dataframe(
        df_style,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "categorie": st.column_config.TextColumn("Catégorie"),
            "designation": st.column_config.TextColumn("Désignation de l'article"),
            "reference": st.column_config.TextColumn("Référence"),
            "quantite": st.column_config.NumberColumn("Stock Restant", format="%d unités"),
            "seuil_alerte": st.column_config.NumberColumn("Seuil d'Alerte"),
            "localisation": st.column_config.TextColumn("Localisation")
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Formulaire de retrait
    st.divider()
    st.subheader("🔄 Déclarer un retrait de matériel")
    
    col_retrait1, col_retrait2, col_retrait3 = st.columns([2, 1, 1])
    
    with col_retrait1:
        # Sélection sécurisée du matériel
        options_materiel = {
            f"{row['designation']} (Réf: {row['reference']}) - Reste: {row['quantite']}": row["id"]
            for _, row in df_filtre.iterrows() if row["quantite"] > 0
        }
        
        if options_materiel:
            choix_label = st.selectbox("Sélectionner l'article à prélever :", list(options_materiel.keys()))
            article_id_selectionne = options_materiel[choix_label]
        else:
            st.info("Aucun article disponible pour un retrait immédiat.")
            article_id_selectionne = None
            
    with col_retrait2:
        nom_chercheur = st.text_input("👤 Votre Prénom & Nom (ou Équipe) :", "").strip()
        
    with col_retrait3:
        quantite_retrait = st.number_input("🔢 Quantité prélevée :", min_value=1, step=1, value=1)
        
    if st.button("🔴 Valider le Retrait", use_container_width=True):
        if not nom_chercheur:
            st.error("Veuillez indiquer votre identité ou le nom de votre équipe avant de valider.")
        elif article_id_selectionne is None:
            st.error("Aucun matériel sélectionné.")
        else:
            # Récupération de l'article ciblé
            df_s = st.session_state.db_stock
            idx = df_s[df_s["id"] == article_id_selectionne].index[0]
            stock_actuel = df_s.at[idx, "quantite"]
            designation_article = df_s.at[idx, "designation"]
            
            if quantite_retrait > stock_actuel:
                st.error(f"Action impossible. Vous demandez {quantite_retrait} unités mais il n'en reste que {stock_actuel} en stock.")
            else:
                # Appliquer la déduction de stock
                nouveau_stock = int(stock_actuel - quantite_retrait)
                st.session_state.db_stock.at[idx, "quantite"] = nouveau_stock
                
                # Enregistrer le mouvement
                add_transaction_log(
                    utilisateur=nom_chercheur,
                    action="Retrait",
                    designation=designation_article,
                    quantite_mouvement=-int(quantite_retrait),
                    nouveau_stock=nouveau_stock
                )
                
                st.success(f"Retrait de {quantite_retrait} unit(s) de '{designation_article}' enregistré avec succès par {nom_chercheur} ! Nouveau stock : {nouveau_stock}")
                st.rerun()

# ==============================================================================
# ESPACE 2 : ADMINISTRATION (AJOUTS, RECHARGE, COMPTABILITÉ & CONFIGURATION)
# ==============================================================================
elif page == "⚙️ Administration":
    st.header("⚙️ Espace Administration & Gestion")
    
    # Onglets d'administration
    tab_editor, tab_add, tab_logs = st.tabs([
        "✏️ Éditeur Excel Interactif", 
        "➕ Ajouter un Nouveau Produit", 
        "📜 Historique des Logs / Audits"
    ])
    
    # ------------------ ONGLET 1 : EDITEUR DIRECT ------------------
    with tab_editor:
        st.write("**🔄 Synchronisation & Modification en masse :**")
        st.write("Modifiez les cases ci-dessous (Double-cliquez pour éditer). N'oubliez pas de cliquer sur le bouton de sauvegarde ci-dessous pour persister vos changements vers le fichier Excel.")
        
        # Éditeur de données natif avec colonnes configurées
        edited_df = st.data_editor(
            st.session_state.db_stock,
            num_rows="dynamic",
            column_config={
                "id": st.column_config.NumberColumn("ID unique", disabled=True),
                "categorie": st.column_config.TextColumn("Catégorie"),
                "designation": st.column_config.TextColumn("Désignation"),
                "reference": st.column_config.TextColumn("Référence"),
                "quantite": st.column_config.NumberColumn("Stock", min_value=0),
                "seuil_alerte": st.column_config.NumberColumn("Seuil d'alerte", min_value=0),
                "localisation": st.column_config.TextColumn("Emplacement physique")
            },
            key="bulk_stock_editor",
            use_container_width=True
        )
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("💾 Sauvegarder les modifications dans l'Excel", use_container_width=True):
                # Validation minimale de l'ID unique
                if edited_df["id"].isnull().any():
                    # Attribuer des IDs automatiques aux lignes ajoutées si vide
                    max_id = st.session_state.db_stock["id"].max() if not st.session_state.db_stock.empty else 0
                    null_indices = edited_df[edited_df["id"].isnull()].index
                    for i, idx in enumerate(null_indices):
                        edited_df.at[idx, "id"] = int(max_id + 1 + i)
                
                # Conversion propre des types
                edited_df["id"] = edited_df["id"].astype(int)
                edited_df["quantite"] = edited_df["quantite"].fillna(0).astype(int)
                edited_df["seuil_alerte"] = edited_df["seuil_alerte"].fillna(0).astype(int)
                
                st.session_state.db_stock = edited_df
                if save_data(st.session_state.db_stock, st.session_state.db_logs):
                    st.success("Fichier Excel mis à jour et synchronisé avec succès !")
                    add_transaction_log("Admin", "Edition en masse", "Base de données", 0, len(edited_df))
                    st.rerun()
                    
        with col_btn2:
            if st.button("🔄 Recharger depuis le fichier Excel (Annuler les modifs)", use_container_width=True):
                df_s, df_l = load_data()
                st.session_state.db_stock = df_s
                st.session_state.db_logs = df_l
                st.info("Données rechargées avec succès depuis l'Excel.")
                st.rerun()

    # ------------------ ONGLET 2 : AJOUT INDIVIDUEL ------------------
    with tab_add:
        st.write("### Ajouter un nouveau produit au stock")
        
        with st.form("new_product_form"):
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                new_designation = st.text_input("Désignation de l'article :").strip()
                new_ref = st.text_input("Référence constructeur :").strip()
                new_cat = st.text_input("Catégorie (ex: Tubes, Boites, Pointes...) :").strip()
            with col_add2:
                new_qty = st.number_input("Quantité initiale en stock :", min_value=0, step=1, value=100)
                new_seuil = st.number_input("Seuil critique d'alerte :", min_value=0, step=1, value=20)
                new_loc = st.text_input("Localisation / Placard :", "Armoire principale").strip()
                
            submitted = st.form_submit_button("➕ Ajouter l'article")
            if submitted:
                if not new_designation or not new_cat:
                    st.error("Veuillez remplir au moins la Désignation et la Catégorie.")
                else:
                    df_s = st.session_state.db_stock
                    new_id = int(df_s["id"].max() + 1) if not df_s.empty else 1
                    
                    row_add = pd.DataFrame([{
                        "id": new_id,
                        "categorie": new_cat,
                        "designation": new_designation,
                        "reference": new_ref,
                        "quantite": int(new_qty),
                        "seuil_alerte": int(new_seuil),
                        "localisation": new_loc
                    }])
                    
                    st.session_state.db_stock = pd.concat([df_s, row_add], ignore_index=True)
                    save_data(st.session_state.db_stock, st.session_state.db_logs)
                    
                    add_transaction_log(
                        utilisateur="Admin",
                        action="Nouveau Produit",
                        designation=new_designation,
                        quantite_mouvement=int(new_qty),
                        nouveau_stock=int(new_qty)
                    )
                    
                    st.success(f"Nouveau produit '{new_designation}' inséré avec succès !")
                    st.rerun()

    # ------------------ ONGLET 3 : HISTORIQUE ET AUDIT ------------------
    with tab_logs:
        st.write("### Historique complet des transactions")
        st.write("Cet historique garde une trace de chaque action (Ajout, retrait, édition) avec horodatage et adresse IP pour garantir la traçabilité.")
        
        # Tri par date et heure décroissantes pour voir le plus récent d'abord
        if not st.session_state.db_logs.empty:
            df_logs_sorted = st.session_state.db_logs.sort_values(by=["date", "heure"], ascending=False)
            st.dataframe(df_logs_sorted, use_container_width=True, hide_index=True)
            
            # Export CSV des logs
            csv_data = df_logs_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exporter l'historique en CSV",
                data=csv_data,
                file_name=f"logs_stock_inmed_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("Aucun log disponible pour le moment.")
