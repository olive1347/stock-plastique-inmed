import streamlit as st
import pandas as pd
import io
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURATION ET SÉCURITÉ
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="GestStock INMED", layout="wide")

# Plages IP autorisées
AUTHORIZED_IP_PREFIXES = [
    "127.0.0.1",
    "139.124.",
    "193.54.",
    "194.254."
]

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
# CHARGEMENT DU FICHIER EXCEL (lecture seule)
# ══════════════════════════════════════════════════════════════
EXCEL_FILE = "Fiche demande labo plastique 2025-2026.xlsx"

@st.cache_data(ttl=300)  # Cache de 5 min
def load_excel():
    try:
        df = pd.read_excel(EXCEL_FILE)
        if df.empty:
            st.warning("⚠️ Le fichier Excel est vide.")
            return pd.DataFrame(columns=["Article", "Stock", "Seuil"])
        # Vérifier les colonnes
        if "Seuil" not in df.columns:
            df["Seuil"] = 10  # Valeur par défaut
        return df.dropna(how="all")
    except FileNotFoundError:
        st.error(f"❌ Fichier {EXCEL_FILE} introuvable. Vérifie le nom ou télécharge-le.")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])
    except Exception as e:
        st.error(f"❌ Erreur de chargement : {e}")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

df = load_excel()

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
# 1. ALERTES STOCKS BAS
# ════════════════════════
if not df.empty and "Stock" in df.columns and "Seuil" in df.columns:
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
# 2. ÉDITION DU STOCK (sans sauvegarde auto)
# ════════════════════════
st.subheader("📝 Éditer le stock")
if df.empty:
    st.warning("⚠️ Aucune donnée à afficher. Vérifie le fichier Excel.")
else:
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

    # Bouton pour télécharger le fichier modifié
    if st.button("📥 Télécharger le stock modifié", type="primary"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            edited_df.to_excel(writer, index=False, sheet_name="Stock")
        st.download_button(
            label="⬇️ Télécharger Excel",
            data=output.getvalue(),
            file_name=f"stock_inmed_modifie_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ════════════════════════
# 3. AFFICHAGE DES DONNÉES ORIGINALES
# ════════════════════════
st.markdown("---")
st.subheader("📋 Données actuelles (lecture seule)")
st.dataframe(df, use_container_width=True)
st.caption(f"Connecté depuis : {client_ip}")
