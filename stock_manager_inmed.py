import streamlit as st
import pandas as pd
import requests

# ══════════════════════════════════════════════════════════════
# CONFIGURATION ET SÉCURITÉ
# ══════════════════════════════════════════════════════════════

# Plages IP autorisées (Ajoutez vos préfixes publics ici)
AUTHORIZED_IP_PREFIXES = [
    "127.0.0.1",
    "139.124.",  # Votre plage publique labo
    "193.54.",
    "194.254."
]

def get_client_ip_details():
    """Récupère l'IP client de manière sécurisée et compatible avec Streamlit Cloud."""
    detected_ip = "127.0.0.1"
    headers = {}
    
    # Tentative via st.request (recommandé pour Streamlit récent)
    try:
        if hasattr(st, "request"):
            headers = dict(st.request.headers)
            ip_headers = ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]
            for h in ip_headers:
                if h in headers:
                    detected_ip = headers[h].split(",")[0].strip()
                    return detected_ip, headers
    except Exception:
        pass

    # Repli vers st.context (si disponible)
    try:
        if hasattr(st, "context"):
            headers = dict(st.context.headers)
            ip_headers = ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]
            for h in ip_headers:
                if h in headers:
                    detected_ip = headers[h].split(",")[0].strip()
                    return detected_ip, headers
    except Exception:
        pass
        
    return detected_ip, headers

def verify_ip_strict(ip):
    """Vérifie si l'IP est dans la liste autorisée."""
    return any(ip.startswith(prefix) for prefix in AUTHORIZED_IP_PREFIXES)

# ══════════════════════════════════════════════════════════════
# INITIALISATION DE L'APPLICATION
# ══════════════════════════════════════════════════════════════

st.set_page_config(page_title="GestStock INMED", layout="wide")

# Vérification de sécurité
client_ip, headers = get_client_ip_details()
is_access_granted = verify_ip_strict(client_ip)

if not is_access_granted:
    st.error("🚫 Accès refusé : Votre connexion ne provient pas du réseau autorisé.")
    st.write(f"IP détectée : `{client_ip}`")
    st.stop()

# ══════════════════════════════════════════════════════════════
# INTERFACE PRINCIPALE
# ══════════════════════════════════════════════════════════════

st.sidebar.image("https://placehold.co/100x100/1e293b/ffffff?text=INMED")
st.sidebar.title("🧪 GestStock INMED")
st.title("Gestion des Consommables Plastiques")

# Exemple de contenu
st.info("Système d'inventaire opérationnel. Réseau sécurisé détecté.")

# Affichage des données (à adapter avec votre fichier Excel)
data = {
    "Article": ["Tube 15mL", "Pointe 200uL", "Boîte Pétri"],
    "Stock": [500, 1200, 80],
    "Seuil": [100, 200, 20]
}
df = pd.DataFrame(data)

st.table(df)

# Note de bas de page
st.caption(f"Connecté depuis : {client_ip}")
