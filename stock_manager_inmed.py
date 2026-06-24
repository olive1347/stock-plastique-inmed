import streamlit as st
import pandas as pd

# ══════════════════════════════════════════════════════════════
# CONFIGURATION ET SÉCURITÉ
# ══════════════════════════════════════════════════════════════

AUTHORIZED_IP_PREFIXES = ["127.0.0.1", "139.124.", "193.54.", "194.254."]

def get_client_ip_details():
    detected_ip = "127.0.0.1"
    try:
        if hasattr(st, "request"):
            headers = dict(st.request.headers)
            if "x-forwarded-for" in headers:
                detected_ip = headers["x-forwarded-for"].split(",")[0].strip()
    except Exception:
        pass
    return detected_ip

# ══════════════════════════════════════════════════════════════
# INITIALISATION
# ══════════════════════════════════════════════════════════════

st.set_page_config(page_title="GestStock INMED", layout="wide")

# Vérification de l'IP
client_ip = get_client_ip_details()
if not any(client_ip.startswith(p) for p in AUTHORIZED_IP_PREFIXES):
    st.error(f"🚫 Accès refusé pour : {client_ip}")
    st.stop()

st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED")
st.sidebar.title("🧪 GestStock INMED")
st.title("Inventaire des Consommables Plastiques")

# ══════════════════════════════════════════════════════════════
# CHARGEMENT ET AFFICHAGE DES DONNÉES
# ══════════════════════════════════════════════════════════════

try:
    # Le fichier CSV généré depuis votre fichier stock-plastique.xlsx
    df = pd.read_csv("stock-plastique.xlsx - Feuil1.csv")
    
    # Nettoyage : Remplir les cellules vides de "Catégories" pour regrouper les articles
    if "Catégories" in df.columns:
        df["Catégories"] = df["Catégories"].ffill()
    
    # Affichage interactif avec possibilité de recherche et tri
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "Prix ": st.column_config.NumberColumn(format="%.2f €"),
        },
        hide_index=True
    )

except FileNotFoundError:
    st.error("Le fichier 'stock-plastique.xlsx - Feuil1.csv' est introuvable. Veuillez vérifier qu'il est présent à la racine du dépôt.")
except Exception as e:
    st.error(f"Erreur lors du chargement des données : {e}")

st.caption(f"Connecté depuis : {client_ip}")
