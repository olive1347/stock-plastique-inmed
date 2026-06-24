import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==============================================================================
# CONFIGURATION DE LA PAGE
# ==============================================================================
st.set_page_config(
    page_title="INMED - Stock Plastique (Sécurité Renforcée)",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_FILE = "stock_plastique_inmed.xlsx"
DEFAULT_COLUMNS = ["id", "categorie", "designation", "reference", "quantite", "seuil_alerte", "localisation"]

# ==============================================================================
# CONFIGURATION DU CONTRÔLE D'ACCÈS RÉSEAU ULTRA-STRICT
# ==============================================================================

AUTHORIZED_IP_PREFIXES = [
    "139.124.", 
    "139.",
    "193.54.",    
    "194.254."    
]

AUTHORIZED_PRIVATE_PREFIXES = [
    "10.",        
    "192.168."    
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

def get_client_ip_details():
    headers = {}
    detected_ip = None
    try:
        headers = dict(st.context.headers)
        ip_headers = ["x-forwarded-for", "x-real-ip", "forwarded", "cf-connecting-ip", "client-ip"]
        for header in ip_headers:
            if header in headers:
                val = headers[header]
                if val:
                    detected_ip = val.split(",")[0].strip()
                    break
    except Exception:
        pass
    if not headers and not detected_ip:
        detected_ip = "127.0.0.1"
    if headers and not detected_ip:
        detected_ip = "NON_IDENTIFIEE"
    return detected_ip, headers

def verify_ip_strict(ip):
    if not ip or ip == "NON_IDENTIFIEE":
        return False
    if ip in ["127.0.0.1", "::1", "localhost"]:
        return True
    for prefix in AUTHORIZED_IP_PREFIXES:
        if ip.startswith(prefix):
            return True
    for prefix in AUTHORIZED_PRIVATE_PREFIXES:
        if ip.startswith(prefix):
            return True
    return False

client_ip, client_headers = get_client_ip_details()
is_access_granted = verify_ip_strict(client_ip)

st.write(f"DEBUG - IP détectée : {client_ip}")
if not is_access_granted:
    st.markdown(
        f"""
        <div style="background-color:#FEE2E2;padding:35px;border-radius:12px;margin-top:40px;border:2px solid #EF4444;text-align:center;">
            <span style="font-size:55px;">🚫</span>
            <h1 style="color:#991B1B;margin-top:10px;font-size:24px;">Accès Réseau Refusé</h1>
            <p style="color:#B91C1C;font-size:15px;margin-top:5px;">
                Votre appareil est connecté depuis un réseau externe non autorisé.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.stop()

def init_database():
    if not os.path.exists(DB_FILE):
        try:
            with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
                df_stock = pd.DataFrame(DEFAULT_DATA)
                df_stock.to_excel(writer, sheet_name="Stock", index=False)
                df_logs = pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])
                df_logs.to_excel(writer, sheet_name="Logs", index=False)
        except Exception as e:
            st.error(f"Erreur d'écriture : {e}")

def load_data():
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
        st.error(f"Erreur chargement : {e}")
        return pd.DataFrame(DEFAULT_DATA), pd.DataFrame(columns=["date", "heure", "ip", "utilisateur", "action", "designation", "quantite_mouvement", "nouveau_stock"])

def save_data(df_stock, df_logs=None):
    try:
        if df_logs is None:
            _, df_logs = load_data()
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            df_stock.to_excel(writer, sheet_name="Stock", index=False)
            df_logs.to_excel(writer, sheet_name="Logs", index=False)
        return True
    except Exception as e:
        st.error(f"Erreur enregistrement : {e}")
        return False

def add_transaction_log(utilisateur, action, designation, quantite_mouvement, nouveau_stock):
    now = datetime.now()
    new_log = {
        "date": now.strftime("%Y-%m-%d"),
        "heure": now.strftime("%H:%M:%S"),
        "ip": client_ip,
        "utilisateur": utilisateur if utilisateur else "Anonyme",
        "action": action,
        "designation": designation,
        "quantite_mouvement": quantite_mouvement,
        "nouveau_stock": nouveau_stock
    }
    st.session_state.db_logs = pd.concat([st.session_state.db_logs, pd.DataFrame([new_log])], ignore_index=True)
    save_data(st.session_state.db_stock, st.session_state.db_logs)

if "db_stock" not in st.session_state or "db_logs" not in st.session_state:
    df_s, df_l = load_data()
    st.session_state.db_stock = df_s
    st.session_state.db_logs = df_l

st.markdown(
    """
    <div style="background-color:#065F46;padding:18px;border-radius:10px;margin-bottom:20px;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">🔬 INMED - Gestionnaire de Consommables Plastiques</h1>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    # Correction de l'erreur TypeError ici : argument supprimé
    st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED")
    st.title("Menu Local")
    page = st.radio("Sélectionnez un espace :", ["🔬 Consultation et Retrait", "⚙️ Administration"])

if page == "🔬 Consultation et Retrait":
    st.subheader("📦 État du Stock & Prélèvement")
    categories_existantes = sorted(list(st.session_state.db_stock["categorie"].dropna().unique()))
    recherche = st.text_input("🔍 Rechercher un article :", "").strip()
    categorie_selectionnee = st.selectbox("📂 Filtrer par Catégorie :", ["Toutes"] + categories_existantes)
    
    df_filtre = st.session_state.db_stock.copy()
    if categorie_selectionnee != "Toutes":
        df_filtre = df_filtre[df_filtre["categorie"] == categorie_selectionnee]
    if recherche:
        df_filtre = df_filtre[df_filtre["designation"].str.contains(recherche, case=False, na=False)]
        
    st.dataframe(df_filtre, use_container_width=True, hide_index=True)
    
    options_materiel = {f"{row['designation']} (Réf: {row['reference']})": row["id"] for _, row in df_filtre.iterrows()}
    if options_materiel:
        choix_label = st.selectbox("Sélectionner l'article à prélever :", list(options_materiel.keys()))
        nom_chercheur = st.text_input("👤 Votre Nom :", "").strip()
        quantite_retrait = st.number_input("🔢 Quantité :", min_value=1, step=1, value=1)
        
        if st.button("🔴 Confirmer le retrait"):
            df_s = st.session_state.db_stock
            idx = df_s[df_s["id"] == options_materiel[choix_label]].index[0]
            st.session_state.db_stock.at[idx, "quantite"] -= quantite_retrait
            add_transaction_log(nom_chercheur, "Retrait", df_s.at[idx, "designation"], -quantite_retrait, st.session_state.db_stock.at[idx, "quantite"])
            st.rerun()

elif page == "⚙️ Administration":
    st.write("Gestion avancée...")
    st.data_editor(st.session_state.db_stock, num_rows="dynamic")
