import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="GestStock INMED",
    layout="wide",
    page_icon="🧪"
)

# Plages IP autorisées (à adapter)
AUTHORIZED_IP_PREFIXES = [
    "127.0.0.1",
    "139.124.",
    "193.54.",
    "194.254."
]

# Fichiers
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"
HISTORY_FILE = "historique.csv"

# ══════════════════════════════════════════════════════════════
# SÉCURITÉ (IP)
# ══════════════════════════════════════════════════════════════
def get_client_ip():
    ip = "127.0.0.1"
    try:
        if hasattr(st, "request"):
            headers = dict(st.request.headers)
            for header in ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]:
                if header in headers:
                    ip = headers[header].split(",")[0].strip()
                    break
    except:
        pass
    return ip

def verify_ip(ip):
    return any(ip.startswith(prefix) for prefix in AUTHORIZED_IP_PREFIXES)

client_ip = get_client_ip()
if not verify_ip(client_ip):
    st.error("🚫 Accès refusé : Votre IP n'est pas autorisée.")
    st.write(f"IP détectée : `{client_ip}`")
    st.stop()

# ══════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════════════════════
@st.cache_data
def load_excel():
    """Charge le fichier Excel et nettoie les données."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        # Nettoyage : supprimer les lignes vides et convertir les colonnes en string
        df = df.dropna(how="all")
        df.columns = df.columns.astype(str)
        # Si la colonne "Seuil" n'existe pas, la créer avec une valeur par défaut (10)
        if "Seuil" not in df.columns:
            df["Seuil"] = 10
        return df
    except FileNotFoundError:
        st.error(f"❌ Fichier {EXCEL_FILE} introuvable. Vérifie le nom ou télécharge-le.")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])
    except Exception as e:
        st.error(f"❌ Erreur de chargement : {e}")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

def save_excel(df):
    """Sauvegarde le DataFrame dans le fichier Excel."""
    try:
        df.to_excel(EXCEL_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"❌ Erreur de sauvegarde : {e}")
        return False

def log_change(user, article, old_stock, new_stock, action):
    """Enregistre une modification dans l'historique."""
    log_entry = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Utilisateur": user,
        "Article": article,
        "Ancien stock": old_stock,
        "Nouveau stock": new_stock,
        "Action": action
    }
    try:
        log_df = pd.read_csv(HISTORY_FILE) if os.path.exists(HISTORY_FILE) else pd.DataFrame()
        log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
        log_df.to_csv(HISTORY_FILE, index=False)
    except Exception as e:
        st.error(f"⚠️ Erreur dans l'historique : {e}")

# ══════════════════════════════════════════════════════════════
# INTERFACE PRINCIPALE
# ══════════════════════════════════════════════════════════════
st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED")
st.sidebar.title("🧪 GestStock INMED")
st.sidebar.markdown("---")
st.sidebar.markdown(f"**IP actuelle :** `{client_ip}`")
st.sidebar.markdown(f"**Dernière MAJ :** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

st.title("📦 Gestion des Consommables Plastiques")
st.markdown("---")

# ════════════════════════
# 1. CHARGEMENT DES DONNÉES
# ════════════════════════
df = load_excel()

if df.empty:
    st.warning("⚠️ Aucune donnée chargée. Ajoutez un fichier Excel valide.")
    st.stop()

# ════════════════════════
# 2. ALERTES STOCKS BAS
# ════════════════════════
if "Stock" in df.columns and "Seuil" in df.columns:
    df["Statut"] = df.apply(
        lambda row: "⚠️ Stock bas" if pd.notna(row["Stock"]) and pd.notna(row["Seuil"]) and row["Stock"] <= row["Seuil"]
        else "✅ OK",
        axis=1
    )
    alert_df = df[df["Statut"] == "⚠️ Stock bas"]
    if not alert_df.empty:
        st.error(f"⚠️ **{len(alert_df)} articles en stock bas ou critique !**")
        st.dataframe(alert_df[["Article", "Stock", "Seuil"]], use_container_width=True)

# ════════════════════════
# 3. ÉDITION DU STOCK
# ════════════════════════
st.subheader("📝 Éditer le stock")
edited_df = st.data_editor(
    df,
    column_config={
        "Article": st.column_config.TextColumn("Article", required=True),
        "Stock": st.column_config.NumberColumn("Stock", required=True, min_value=0),
        "Seuil": st.column_config.NumberColumn("Seuil critique", required=True, min_value=0),
    },
    use_container_width=True,
    num_rows="dynamic",
    key="stock_editor"
)

# ════════════════════════
# 4. SAUVEGARDE + HISTORIQUE
# ════════════════════════
if st.button("💾 Sauvegarder les modifications", type="primary"):
    changes = []
    for index, row in edited_df.iterrows():
        if index < len(df):
            old_row = df.iloc[index]
            if row["Stock"] != old_row["Stock"]:
                changes.append({
                    "article": row["Article"],
                    "old_stock": old_row["Stock"],
                    "new_stock": row["Stock"],
                    "action": "Modification"
                })

    if changes:
        # Sauvegarder l'Excel
        if save_excel(edited_df):
            # Mettre à jour l'historique
            for change in changes:
                log_change(
                    user=client_ip,  # Ou un nom d'utilisateur si auth activée
                    article=change["article"],
                    old_stock=change["old_stock"],
                    new_stock=change["new_stock"],
                    action=change["action"]
                )
            st.success(f"✅ **{len(changes)} modifications sauvegardées !**")
            st.rerun()  # Recharger pour afficher les nouvelles données
    else:
        st.info("ℹ️ Aucune modification détectée.")

# ════════════════════════
# 5. AFFICHAGE DE L'HISTORIQUE
# ════════════════════════
st.markdown("---")
st.subheader("📜 Historique des modifications")
if os.path.exists(HISTORY_FILE):
    history_df = pd.read_csv(HISTORY_FILE)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info("Aucune modification enregistrée pour l'instant.")
else:
    st.info("Aucun historique disponible.")
