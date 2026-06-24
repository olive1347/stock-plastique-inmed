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
# CHARGEMENT DU STOCK
# ======================
@st.cache_data(ttl=300)
def load_excel():
    try:
        df = pd.read_excel(EXCEL_FILE)

        # Nettoyer les données
        df = df.dropna(how='all')
        df = df.dropna(subset=[df.columns[0]])

        # Renommer les 2 premières colonnes
        df = df.rename(columns={
            df.columns[0]: "Article",
            df.columns[1]: "Stock"
        })

        # Convertir Stock en nombre
        df["Stock"] = pd.to_numeric(df["Stock"], errors='coerce')

        # Supprimer les lignes où Article ou Stock est vide
        df = df.dropna(subset=["Article", "Stock"])

        return df

    except FileNotFoundError:
        st.error(f"❌ Fichier '{EXCEL_FILE}' introuvable !")
        return pd.DataFrame(columns=["Article", "Stock", "Information", "Cdt", "Catégories"])
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame(columns=["Article", "Stock", "Information", "Cdt", "Catégories"])

# ======================
# GESTION DES COMMANDES
# ======================
def load_commandes():
    try:
        return pd.read_csv(COMMANDES_FILE)
    except:
        return pd.DataFrame(columns=["Date", "Utilisateur", "Article", "Quantité", "Information", "Cdt", "Statut"])

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

mode = st.sidebar.radio("Mode", ["🛒 Passer une commande", "👨‍🔬 Gérer les commandes"])

# ======================
# MODE UTILISATEUR
# ======================
if mode == "🛒 Passer une commande":
    st.title("📝 Passer une commande de consommables")
    st.markdown("---")

    stock_df = load_excel()

    if stock_df.empty:
        st.error("❌ Aucun article disponible. Vérifie ton fichier Excel.")
        st.stop()

    # Afficher TOUTES les colonnes utiles (Article, Information, Cdt, Catégories, Stock)
    st.subheader("📦 Stock disponible")

    # Sélectionner les colonnes à afficher (si elles existent)
    display_columns = ["Article"]
    for col in ["Information", "Cdt", "Catégories", "Stock"]:
        if col in stock_df.columns:
            display_columns.append(col)

    st.dataframe(stock_df[display_columns], use_container_width=True)

    st.subheader("✏️ Ma commande")
    with st.form("commande_form"):
        utilisateur = st.text_input("👤 Votre nom ou service", placeholder="Ex: Labo Biologie")

        # Sélection de l'article avec toutes les infos
        selected_row = st.selectbox(
            "📦 Sélectionnez un article",
            options=stock_df.index,
            format_func=lambda x: f"{stock_df.loc[x, 'Article']} - {stock_df.loc[x, 'Information'] if 'Information' in stock_df.columns else ''} - {stock_df.loc[x, 'Cdt'] if 'Cdt' in stock_df.columns else ''}",
            index=0
        )

        quantite = st.number_input(
            "🔢 Quantité souhaitée",
            min_value=1,
            max_value=int(stock_df.loc[selected_row, "Stock"]),
            value=1
        )

        commentaire = st.text_area("💬 Commentaire (optionnel)", placeholder="Ex: Urgent pour demain")

        if st.form_submit_button("📤 Valider la commande"):
            if not utilisateur:
                st.error("❌ Veuillez indiquer votre nom ou service.")
            else:
                article = stock_df.loc[selected_row, "Article"]
                info = stock_df.loc[selected_row, "Information"] if "Information" in stock_df.columns else ""
                cdt = stock_df.loc[selected_row, "Cdt"] if "Cdt" in stock_df.columns else ""

                commandes = load_commandes()
                commandes = pd.concat([
                    commandes,
                    pd.DataFrame([{
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Utilisateur": utilisateur,
                        "Article": article,
                        "Information": info,
                        "Cdt": cdt,
                        "Quantité": quantite,
                        "Commentaire": commentaire,
                        "Statut": "⏳ En attente"
                    }])
                ], ignore_index=True)
                save_commandes(commandes)

                st.success(f"✅ Commande enregistrée pour {quantite}x {article} !")
                st.info(f"📋 Détails : {info} - {cdt}")

# ======================
# MODE ADMIN
# ======================
elif mode == "👨‍🔬 Gérer les commandes":
    st.title("📊 Gestion des commandes")
    st.markdown("---")

    stock_df = load_excel()
    commandes_df = load_commandes()

    # Commandes en attente
    st.subheader("⏳ Commandes en attente")
    en_attente = commandes_df[commandes_df["Statut"] == "⏳ En attente"]

    if not en_attente.empty:
        # Afficher toutes les colonnes pertinentes
        admin_display_cols = ["Date", "Utilisateur", "Article", "Information", "Cdt", "Quantité", "Statut"]
        admin_display_cols = [col for col in admin_display_cols if col in commandes_df.columns]
        st.dataframe(en_attente[admin_display_cols], use_container_width=True)

        if st.button("✅ Valider toutes les commandes", type="primary"):
            for _, row in en_attente.iterrows():
                article = row["Article"]
                quantite = row["Quantité"]
                if "Article" in stock_df.columns and "Stock" in stock_df.columns:
                    stock_df.loc[stock_df["Article"] == article, "Stock"] -= quantite
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
    else:
        st.info("ℹ️ Aucune commande en attente.")

    # Historique complet
    st.subheader("📜 Historique des commandes")
    if not commandes_df.empty:
        st.dataframe(commandes_df, use_container_width=True)
        st.download_button(
            "📥 Télécharger historique (CSV)",
            commandes_df.to_csv(index=False).encode(),
            f"historique_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
    else:
        st.info("ℹ️ Aucune commande enregistrée.")
