import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==============================================================================
# CONFIGURATION DE LA PAGE
# ==============================================================================
st.set_page_config(
    page_title="INMED - Gestion du Stock de Plastique",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed" # Idéal pour les téléphones portables
)

# ==============================================================================
# CONFIGURATION DE LA SÉCURITÉ ET DES FICHIERS
# ==============================================================================
DB_FILE = "stock_plastique_inmed.xlsx"
DEFAULT_COLUMNS = ["id", "categorie", "designation", "reference", "quantite", "seuil_alerte", "localisation"]

# Code d'accès chercheur par défaut pour l'extérieur du laboratoire (ex: 5G, domicile)
CHERCHEUR_PASSWORD = "INMED2026"

# Liste des débuts d'adresses IP publiques du laboratoire INMED / AMU / INSERM (exemples modifiables)
# Si l'IP du chercheur commence par l'une de ces chaînes, l'accès est automatique sans mot de passe
LAB_IP_PREFIXES = [
    "139.124.",  # Réseau Aix-Marseille Université (AMU)
    "193.54.",   # Réseau académique INSERM/CNRS
    "194.254."   # Autre plage académique commune
]

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
        headers = st.context.headers
        if "x-forwarded-for" in headers:
            return headers["x-forwarded-for"].split(",")[0].strip()
        if "x-real-ip" in headers:
            return headers["x-real-ip"]
    except Exception:
        pass
    return "127.0.0.1"


def is_ip_authorized(ip):
    """Vérifie si l'IP appartient aux plages autorisées du laboratoire"""
    if ip == "127.0.0.1" or ip.startswith("192.168.") or ip.startswith("10."):
        return True # Autorise le réseau local de développement et de test
    for prefix in LAB_IP_PREFIXES:
        if ip.startswith(prefix):
            return True
    return False


def init_database():
    """Initialise le fichier Excel de base s'il est manquant"""
    if not os.path.exists(DB_FILE):
        try:
            with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
                df_stock = pd.DataFrame(DEFAULT_DATA)
                df_stock.to_excel(writer, sheet_name="Stock", index=False)
                df_logs = pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])
                df_logs.to_excel(writer, sheet_name="Logs", index=False)
        except Exception as e:
            st.error(f"Impossible d'écrire le fichier d'initialisation Excel : {e}")


def load_data():
    """Charge la base de données Excel de manière sécurisée"""
    init_database()
    try:
        df_stock = pd.read_excel(DB_FILE, sheet_name="Stock")
        for col in DEFAULT_COLUMNS:
            if col not in df_stock.columns:
                df_stock[col] = "" if col != "quantite" and col != "seuil_alerte" else 0
        
        df_stock["id"] = df_stock["id"].astype(int)
        df_stock["quantite"] = pd.to_numeric(df_stock["quantite"], errors="coerce").fillna(0).astype(int)
        df_stock["seuil_alerte"] = pd.to_numeric(df_stock["seuil_alerte"], errors="coerce").fillna(0).astype(int)
        
        try:
            df_logs = pd.read_excel(DB_FILE, sheet_name="Logs")
        except Exception:
            df_logs = pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])
            
        return df_stock, df_logs
    except Exception as e:
        st.error(f"Erreur lors du chargement des données Excel : {e}")
        return pd.DataFrame(DEFAULT_DATA), pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])


def save_data(df_stock, df_logs=None):
    """Enregistre le stock et les logs dans le fichier Excel"""
    try:
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
    
    st.session_state.db_logs = pd.concat([st.session_state.db_logs, pd.DataFrame([new_log])], ignore_index=True)
    save_data(st.session_state.db_stock, st.session_state.db_logs)


# ==============================================================================
# GESTION DES ÉTATS DE SESSION
# ==============================================================================
if "db_stock" not in st.session_state or "db_logs" not in st.session_state:
    df_s, df_l = load_data()
    st.session_state.db_stock = df_s
    st.session_state.db_logs = df_l

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Vérification automatique de l'IP de connexion
current_user_ip = get_user_ip()
is_internal = is_ip_authorized(current_user_ip)

if is_internal:
    st.session_state.authenticated = True

# ==============================================================================
# ÉCRAN DE VERROUILLAGE (HORS LABORATOIRE / 5G / DOMICILE)
# ==============================================================================
if not st.session_state.authenticated:
    st.markdown(
        """
        <div style="background-color:#F3F4F6;padding:30px;border-radius:15px;margin-top:40px;border:1px solid #E5E7EB;text-align:center;">
            <span style="font-size:50px;">🔒</span>
            <h2 style="color:#1F2937;margin-top:10px;">Accès Extérieur Sécurisé</h2>
            <p style="color:#4B5563;font-size:15px;">Vous tentez d'accéder au gestionnaire de stock en dehors du réseau de l'INMED (ex: 5G ou domicile).<br>
            Veuillez entrer le <b>code d'accès chercheur</b> pour déverrouiller l'application.</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    col_lock1, col_lock2, col_lock3 = st.columns([1, 2, 1])
    with col_lock2:
        code_saisi = st.text_input("Saisissez le code d'accès :", type="password", key="security_bypass_input")
        if st.button("🔓 Valider le code", use_container_width=True):
            if code_saisi == CHERCHEUR_PASSWORD:
                st.session_state.authenticated = True
                st.success("Accès autorisé ! Bienvenue.")
                st.rerun()
            else:
                st.error("Code d'accès incorrect. Veuillez contacter l'administrateur de la plateforme.")
    st.stop()  # Bloque complètement l'exécution du reste de l'application tant qu'on n'est pas authentifié.

# ==============================================================================
# EN-TÊTE GRAPHIQUE (APPRÈS AUTHENTIFICATION)
# ==============================================================================
st.markdown(
    """
    <div style="background-color:#1E3A8A;padding:18px;border-radius:10px;margin-bottom:20px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">🔬 INMED - Gestionnaire de Consommables Plastiques</h1>
        <p style="color:#BFDBFE;margin:5px 0 0 0;font-size:13px;">Suivi en temps réel et traçabilité des consommables</p>
    </div>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# BARRE LATÉRALE - NAVIGATION ET INFOS
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/plasticine/100/test-tube.png", width=60)
    st.title("Menu")
    
    page = st.radio(
        "Sélectionnez un espace :",
        ["🔬 Consultation et Retrait", "⚙️ Administration"]
    )
    
    st.divider()
    st.markdown("### 💻 Informations")
    st.caption(f"**IP détectée :** `{current_user_ip}`")
    if is_internal:
        st.success("🟢 Connecté via le réseau INMED")
    else:
        st.warning("🔵 Connecté en dehors du laboratoire")

# ==============================================================================
# ESPACE 1 : CONSULTATION ET RETRAIT (POUR TOUS LES CHERCHEURS)
# ==============================================================================
if page == "🔬 Consultation et Retrait":
    st.subheader("📦 État du Stock & Prélèvement")
    
    if isinstance(st.session_state.db_stock, pd.DataFrame):
        categories_existantes = sorted(list(st.session_state.db_stock["categorie"].dropna().unique()))
    else:
        categories_existantes = []
        
    # Filtres de recherche (adaptés mobiles)
    recherche = st.text_input("🔍 Rechercher un article (nom, marque, ref...) :", "").strip()
    categorie_selectionnee = st.selectbox("📂 Filtrer par Catégorie :", ["Toutes"] + categories_existantes)
        
    df_filtre = st.session_state.db_stock.copy()
    if categorie_selectionnee != "Toutes":
        df_filtre = df_filtre[df_filtre["categorie"] == categorie_selectionnee]
    if recherche:
        df_filtre = df_filtre[
            df_filtre["designation"].str.contains(recherche, case=False, na=False) |
            df_filtre["reference"].str.contains(recherche, case=False, na=False)
        ]
        
    # Alerte de stock bas
    items_critiques = df_filtre[df_filtre["quantite"] <= df_filtre["seuil_alerte"]]
    if not items_critiques.empty:
        st.warning(f"⚠️ **Attention :** {len(items_critiques)} consommables ont atteint leur seuil d'alerte et doivent être commandés !")
        
    # Affichage du tableau
    st.markdown("### Matériel en stock")
    
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
            "quantite": st.column_config.NumberColumn("Stock Restant", format="%d u."),
            "seuil_alerte": st.column_config.NumberColumn("Seuil"),
            "localisation": st.column_config.TextColumn("Localisation")
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Formulaire de retrait
    st.divider()
    st.subheader("🔄 Déclarer un prélèvement de matériel")
    
    options_materiel = {
        f"{row['designation']} (Réf: {row['reference']}) - Reste: {row['quantite']}": row["id"]
        for _, row in df_filtre.iterrows() if row["quantite"] > 0
    }
    
    if options_materiel:
        choix_label = st.selectbox("Sélectionner l'article à prélever :", list(options_materiel.keys()))
        article_id_selectionne = options_materiel[choix_label]
        
        nom_chercheur = st.text_input("👤 Votre Nom (ou Équipe) :", "").strip()
        quantite_retrait = st.number_input("🔢 Quantité prélevée :", min_value=1, step=1, value=1)
        
        if st.button("🔴 Confirmer le retrait", use_container_width=True):
            if not nom_chercheur:
                st.error("Veuillez indiquer votre nom ou équipe avant de valider.")
            else:
                df_s = st.session_state.db_stock
                idx = df_s[df_s["id"] == article_id_selectionne].index[0]
                stock_actuel = df_s.at[idx, "quantite"]
                designation_article = df_s.at[idx, "designation"]
                
                if quantite_retrait > stock_actuel:
                    st.error(f"Action impossible. Vous demandez {quantite_retrait} u. mais il n'en reste que {stock_actuel} u.")
                else:
                    nouveau_stock = int(stock_actuel - quantite_retrait)
                    st.session_state.db_stock.at[idx, "quantite"] = nouveau_stock
                    
                    add_transaction_log(
                        utilisateur=nom_chercheur,
                        action="Retrait",
                        designation=designation_article,
                        quantite_mouvement=-int(quantite_retrait),
                        nouveau_stock=nouveau_stock
                    )
                    
                    st.success(f"Retrait de {quantite_retrait} unité(s) enregistré ! Nouveau stock : {nouveau_stock}")
                    st.rerun()
    else:
        st.info("Aucun article disponible pour le retrait.")

# ==============================================================================
# ESPACE 2 : ADMINISTRATION (AJOUTS, EDITIONS, LOGS)
# ==============================================================================
elif page == "⚙️ Administration":
    st.subheader("⚙️ Administration & Gestion du Stock")
    
    tab_editor, tab_add, tab_logs = st.tabs([
        "✏️ Édition Directe", 
        "➕ Nouveau Produit", 
        "📜 Historique & Audit"
    ])
    
    # ------------------ ONGLET 1 : EDITEUR DIRECT ------------------
    with tab_editor:
        st.write("Modifiez directement les cases dans le tableau ci-dessous, puis cliquez sur **Sauvegarder**.")
        
        edited_df = st.data_editor(
            st.session_state.db_stock,
            num_rows="dynamic",
            column_config={
                "id": st.column_config.NumberColumn("ID unique", disabled=True),
                "categorie": st.column_config.TextColumn("Catégorie"),
                "designation": st.column_config.TextColumn("Désignation"),
                "reference": st.column_config.TextColumn("Référence"),
                "quantite": st.column_config.NumberColumn("Stock", min_value=0),
                "seuil_alerte": st.column_config.NumberColumn("Seuil", min_value=0),
                "localisation": st.column_config.TextColumn("Emplacement")
            },
            key="bulk_stock_editor",
            use_container_width=True
        )
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Sauvegarder les modifications", use_container_width=True):
                if edited_df["id"].isnull().any():
                    max_id = st.session_state.db_stock["id"].max() if not st.session_state.db_stock.empty else 0
                    null_indices = edited_df[edited_df["id"].isnull()].index
                    for i, idx in enumerate(null_indices):
                        edited_df.at[idx, "id"] = int(max_id + 1 + i)
                
                edited_df["id"] = edited_df["id"].astype(int)
                edited_df["quantite"] = edited_df["quantite"].fillna(0).astype(int)
                edited_df["seuil_alerte"] = edited_df["seuil_alerte"].fillna(0).astype(int)
                
                st.session_state.db_stock = edited_df
                if save_data(st.session_state.db_stock, st.session_state.db_logs):
                    st.success("Modifications persistées dans le fichier Excel !")
                    add_transaction_log("Admin", "Edition en masse", "Base de données", 0, len(edited_df))
                    st.rerun()
                    
        with col_btn2:
            if st.button("🔄 Annuler & Recharger depuis le fichier Excel", use_container_width=True):
                df_s, df_l = load_data()
                st.session_state.db_stock = df_s
                st.session_state.db_logs = df_l
                st.info("Données rechargées.")
                st.rerun()

    # ------------------ ONGLET 2 : AJOUT INDIVIDUEL ------------------
    with tab_add:
        st.write("### Ajouter une nouvelle référence")
        
        with st.form("new_product_form"):
            new_designation = st.text_input("Désignation de l'article :").strip()
            new_ref = st.text_input("Référence constructeur :").strip()
            new_cat = st.text_input("Catégorie :").strip()
            new_qty = st.number_input("Quantité initiale :", min_value=0, step=1, value=100)
            new_seuil = st.number_input("Seuil d'alerte :", min_value=0, step=1, value=20)
            new_loc = st.text_input("Emplacement :", "Armoire principale").strip()
                
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
                    
                    st.success(f"'{new_designation}' ajouté au catalogue !")
                    st.rerun()

    # ------------------ ONGLET 3 : HISTORIQUE ET AUDIT ------------------
    with tab_logs:
        st.write("### Historique complet des transactions (Logs)")
        
        if not st.session_state.db_logs.empty:
            df_logs_sorted = st.session_state.db_logs.sort_values(by=["date", "heure"], ascending=False)
            st.dataframe(df_logs_sorted, use_container_width=True, hide_index=True)
            
            csv_data = df_logs_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exporter l'historique en CSV",
                data=csv_data,
                file_name=f"logs_stock_inmed_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("Aucune transaction enregistrée.")
