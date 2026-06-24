import streamlit as st
import pandas as pd
import io
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="GestStock INMED", layout="wide")

# Plages IP autorisées
AUTHORIZED_IP_PREFIXES = [
    "127.0.0.1",
    "139.124.",
    "193.54.",
    "194.254."
]

# Fichier Excel
EXCEL_FILE = "stock-plastique.xlsx"
COMMANDES_FILE = "commandes.csv"

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
@st.cache_data(ttl=300)
def load_excel():
    try:
        df = pd.read_excel(EXCEL_FILE)

        if df.empty:
            st.error("❌ Le fichier Excel est vide.")
            return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

        # Détecter les colonnes
        available_columns = df.columns.tolist()
        st.info(f"ℹ️ Colonnes détectées : **{available_columns}**")

        # Mapping intelligent (ADAPTÉ À TON FICHIER)
        column_mapping = {}
        for col in available_columns:
            col_lower = str(col).lower()
            if any(word in col_lower for word in [
                "article", "produit", "nom", "référence", "réf", "item",
                "consommable", "matériel", "designation", "désignation",
                "libellé", "description", "type"
            ]):
                column_mapping[col] = "Article"
            elif any(word in col_lower for word in [
                "stock", "quantité", "quantite", "dispo", "disponible",
                "available", "qté", "qte", "quantité demandée"
            ]):
                column_mapping[col] = "Stock"
            elif any(word in col_lower for word in ["seuil", "minimum", "min", "alerte", "limite"]):
                column_mapping[col] = "Seuil"

        # Appliquer le mapping
        if column_mapping:
            df = df.rename(columns=column_mapping)
        else:
            st.warning("⚠️ Impossible de deviner les colonnes. Utilisation des 2 premières colonnes.")
            if len(available_columns) >= 2:
                df = df.rename(columns={available_columns[0]: "Article", available_columns[1]: "Stock"})
            else:
                st.error("❌ Le fichier doit avoir au moins 2 colonnes.")
                return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

        # Vérifier les colonnes requises
        if "Article" not in df.columns or "Stock" not in df.columns:
            missing = []
            if "Article" not in df.columns:
                missing.append("Article")
            if "Stock" not in df.columns:
                missing.append("Stock")
            st.error(f"❌ Colonnes manquantes : {missing}. Disponibles : {list(df.columns)}")
            return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

        if "Seuil" not in df.columns:
            df["Seuil"] = 10

        return df.dropna(how="all")

    except FileNotFoundError:
        st.error(f"❌ Fichier '{EXCEL_FILE}' introuvable !")
        st.markdown(f"**Solution :** Place le fichier dans le même dossier que le script.")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

def load_commandes():
    try:
        return pd.read_csv(COMMANDES_FILE)
    except:
        return pd.DataFrame(columns=["Date", "Utilisateur", "Article", "Quantité", "Commentaire", "Statut"])

def save_commandes(df):
    try:
        df.to_csv(COMMANDES_FILE, index=False)
        return True
    except:
        return False

# ══════════════════════════════════════════════════════════════
# INTERFACE
# ══════════════════════════════════════════════════════════════
st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED")
st.sidebar.title("🧪 GestStock INMED")
st.sidebar.markdown(f"**IP :** `{client_ip}`")
st.sidebar.markdown(f"**Date :** {datetime.now().strftime('%d/%m/%Y')}")

mode = st.sidebar.radio("Mode", options=["🛒 Passer une commande", "👨‍🔬 Gérer les commandes (Admin)"])

# ════════════════════════
# MODE UTILISATEUR
# ════════════════════════
if mode == "🛒 Passer une commande":
    st.title("📝 Passer une commande de consommables")
    st.markdown("---")

    stock_df = load_excel()
    if stock_df.empty or "Article" not in stock_df.columns:
        st.error("❌ Aucun article disponible.")
        st.stop()

    st.subheader("📦 Stock disponible")
    st.dataframe(stock_df[["Article", "Stock"]], use_container_width=True)

    st.subheader("✏️ Ma commande")
    with st.form("commande_form"):
        nom_utilisateur = st.text_input("👤 Votre nom ou service", placeholder="Ex: Labo Biologie")
        article = st.selectbox("📦 Article", options=stock_df["Article"].tolist(), index=0)
        quantite = st.number_input("🔢 Quantité souhaitée", min_value=1, max_value=1000, value=1)
        commentaire = st.text_area("💬 Commentaire (optionnel)", placeholder="Ex: Urgent")

        submitted = st.form_submit_button("📤 Valider la commande")

    if submitted:
        if not nom_utilisateur:
            st.error("❌ Veuillez indiquer votre nom.")
        else:
            stock_dispo = stock_df[stock_df["Article"] == article]["Stock"].values[0]
            if quantite > stock_dispo:
                st.error(f"❌ Stock insuffisant ! Disponible : {stock_dispo}")
            else:
                commandes = load_commandes()
                nouvelle_commande = {
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Utilisateur": nom_utilisateur,
                    "Article": article,
                    "Quantité": quantite,
                    "Commentaire": commentaire,
                    "Statut": "⏳ En attente"
                }
                commandes = pd.concat([commandes, pd.DataFrame([nouvelle_commande])], ignore_index=True)
                save_commandes(commandes)

                st.success(f"✅ Commande enregistrée pour {quantite}x {article} !")
                st.info("⚠️ Votre commande sera traitée par l'administrateur.")
                st.subheader("📋 Récapitulatif")
                st.dataframe(pd.DataFrame([nouvelle_commande]), use_container_width=True)

# ════════════════════════
# MODE ADMIN
# ════════════════════════
elif mode == "👨‍🔬 Gérer les commandes (Admin)":
    st.title("📊 Gestion des commandes")
    st.markdown("---")

    stock_df = load_excel()
    commandes_df = load_commandes()

    st.subheader("⏳ Commandes en attente")
    commandes_en_attente = commandes_df[commandes_df["Statut"] == "⏳ En attente"]

    if commandes_en_attente.empty:
        st.info("ℹ️ Aucune commande en attente.")
    else:
        st.dataframe(commandes_en_attente, use_container_width=True)

        if st.button("✅ Valider toutes les commandes", type="primary"):
            for index, row in commandes_en_attente.iterrows():
                article = row["Article"]
                quantite = row["Quantité"]
                if "Article" in stock_df.columns and "Stock" in stock_df.columns:
                    stock_df.loc[stock_df["Article"] == article, "Stock"] -= quantite
                commandes_df.loc[index, "Statut"] = "✅ Validée"

            save_commandes(commandes_df)
            st.success(f"✅ {len(commandes_en_attente)} commandes validées !")

            st.subheader("📦 Stock après validation")
            st.dataframe(stock_df[["Article", "Stock"]], use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                stock_df.to_excel(writer, index=False, sheet_name="Stock")
            st.download_button(
                label="📥 Télécharger le stock mis à jour",
                data=output.getvalue(),
                file_name=f"stock_mis_a_jour_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.subheader("📜 Historique des commandes")
    if not commandes_df.empty:
        st.dataframe(commandes_df, use_container_width=True)
    else:
        st.info("ℹ️ Aucune commande enregistrée.")

    if not commandes_df.empty:
        csv_data = commandes_df.to_csv(index=False)
        st.download_button(
            label="📥 Télécharger l'historique (CSV)",
            data=csv_data,
            file_name=f"historique_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
