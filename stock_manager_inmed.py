import streamlit as st
import pandas as pd
import io
from datetime import datetime

# ======================
# CONFIGURATION
# ======================
st.set_page_config(page_title="GestStock INMED", layout="wide")

AUTHORIZED_IP_PREFIXES = ["127.0.0.1", "139.124.", "193.54.", "194.254."]
EXCEL_FILE = "stock-plastique.xlsx"
COMMANDES_FILE = "commandes.csv"

# ======================
# SÉCURITÉ IP
# ======================
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

client_ip = get_client_ip()
if not any(client_ip.startswith(prefix) for prefix in AUTHORIZED_IP_PREFIXES):
    st.error("🚫 Accès refusé : IP non autorisée.")
    st.write(f"IP détectée : `{client_ip}`")
    st.stop()

# ======================
# FONCTIONS
# ======================
@st.cache_data(ttl=300)
def load_excel():
    try:
        df = pd.read_excel(EXCEL_FILE)

        if df.empty:
            st.error("❌ Le fichier Excel est vide.")
            return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

        # Détection automatique des colonnes
        cols = {col.lower(): col for col in df.columns}
        available_cols = list(cols.keys())

        # Mapping intelligent
        article_col = None
        stock_col = None

        for col in available_cols:
            if any(word in col for word in ["article", "produit", "nom", "designation", "libellé", "consommable", "matériel", "référence"]):
                article_col = cols[col]
            elif any(word in col for word in ["stock", "quantité", "quantite", "dispo", "qte", "qté", "available"]):
                stock_col = cols[col]

        # Si pas trouvé, utiliser les 2 premières colonnes
        if not article_col or not stock_col:
            if len(df.columns) >= 2:
                article_col = df.columns[0]
                stock_col = df.columns[1]
                st.warning(f"⚠️ Colonnes détectées automatiquement : **{article_col}** → Article, **{stock_col}** → Stock")
            else:
                st.error("❌ Le fichier doit avoir au moins 2 colonnes.")
                return pd.DataFrame(columns=["Article", "Stock", "Seuil"])

        # Renommer les colonnes
        df = df.rename(columns={article_col: "Article", stock_col: "Stock"})

        # Ajouter Seuil si absent
        if "Seuil" not in df.columns:
            df["Seuil"] = 10

        return df.dropna(how="all")

    except FileNotFoundError:
        st.error(f"❌ Fichier '{EXCEL_FILE}' introuvable !")
        st.markdown("**Solution :** Vérifie que le fichier est dans le même dossier que le script.")
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

# ======================
# INTERFACE
# ======================
st.sidebar.title("🧪 GestStock INMED")
st.sidebar.markdown(f"**IP :** `{client_ip}`")
st.sidebar.markdown(f"**Date :** {datetime.now().strftime('%d/%m/%Y')}")

mode = st.sidebar.radio("Mode", ["🛒 Passer une commande", "👨‍🔬 Gérer les commandes (Admin)"])

# ======================
# MODE UTILISATEUR
# ======================
if mode == "🛒 Passer une commande":
    st.title("📝 Passer une commande")
    st.markdown("---")

    stock_df = load_excel()
    if stock_df.empty or "Article" not in stock_df.columns:
        st.error("❌ Aucun article disponible.")
        st.stop()

    st.subheader("📦 Stock disponible")
    st.dataframe(stock_df[["Article", "Stock"]], use_container_width=True)

    st.subheader("✏️ Nouvelle commande")
    with st.form("commande_form"):
        utilisateur = st.text_input("👤 Nom/Service", placeholder="Labo Biologie")
        article = st.selectbox("📦 Article", stock_df["Article"].tolist())
        quantite = st.number_input("🔢 Quantité", min_value=1, value=1)
        commentaire = st.text_area("💬 Commentaire", placeholder="Optionnel")

        if st.form_submit_button("📤 Valider"):
            if not utilisateur:
                st.error("❌ Nom obligatoire !")
            else:
                stock_dispo = stock_df[stock_df["Article"] == article]["Stock"].values[0]
                if quantite > stock_dispo:
                    st.error(f"❌ Stock insuffisant ({stock_dispo} disponibles)")
                else:
                    commandes = load_commandes()
                    commandes = pd.concat([
                        commandes,
                        pd.DataFrame([{
                            "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Utilisateur": utilisateur,
                            "Article": article,
                            "Quantité": quantite,
                            "Commentaire": commentaire,
                            "Statut": "⏳ En attente"
                        }])
                    ], ignore_index=True)
                    save_commandes(commandes)
                    st.success(f"✅ Commande de {quantite}x {article} enregistrée !")

# ======================
# MODE ADMIN
# ======================
elif mode == "👨‍🔬 Gérer les commandes (Admin)":
    st.title("📊 Gestion des commandes")
    st.markdown("---")

    stock_df = load_excel()
    commandes_df = load_commandes()

    # Commandes en attente
    st.subheader("⏳ Commandes en attente")
    en_attente = commandes_df[commandes_df["Statut"] == "⏳ En attente"]

    if not en_attente.empty:
        st.dataframe(en_attente, use_container_width=True)
        if st.button("✅ Valider toutes les commandes", type="primary"):
            for _, row in en_attente.iterrows():
                stock_df.loc[stock_df["Article"] == row["Article"], "Stock"] -= row["Quantité"]
                commandes_df.loc[commandes_df.index == row.name, "Statut"] = "✅ Validée"
            save_commandes(commandes_df)
            st.success(f"✅ {len(en_attente)} commandes validées !")

            # Téléchargement du stock mis à jour
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                stock_df.to_excel(writer, index=False, sheet_name="Stock")
            st.download_button(
                "📥 Télécharger stock mis à jour",
                output.getvalue(),
                f"stock_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # Historique
    st.subheader("📜 Historique complet")
    st.dataframe(commandes_df, use_container_width=True)
    if not commandes_df.empty:
        st.download_button(
            "📥 Télécharger historique (CSV)",
            commandes_df.to_csv(index=False).encode(),
            f"historique_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
