"""
scanner_etiquettes.py — Module de scan d'étiquettes pour inventaire labo
Intégrable dans l'app INMED multi-onglets ou en standalone.
"""

import streamlit as st
import anthropic
import base64
import json
import pandas as pd
import os
from datetime import datetime

# ── Fichier CSV de persistance ────────────────────────────────────────────────
INVENTORY_FILE = "inventaire_labo.csv"

CHAMPS = [
    "date_scan", "nom_produit", "fabricant", "reference", "numero_lot",
    "numero_cas", "formule", "purete", "quantite", "unite",
    "date_peremption", "stockage", "emplacement", "notes",
]

# ── CSS personnalisé ───────────────────────────────────────────────────────────
CSS = """
<style>
:root { --indigo: #2D3A8C; --teal: #00A8A8; --light: #F5F7FA; --text: #1A1F36; --muted: #6B7280; }
.lab-header { background: linear-gradient(135deg, var(--indigo) 0%, #1a2460 100%); color: white; padding: 1.2rem 1.6rem; border-radius: 10px; margin-bottom: 1.4rem; }
.result-card { background: var(--light); border-left: 4px solid var(--teal); border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; }
.label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; color: var(--muted); }
.value { font-size: 0.95rem; color: var(--text); font-family: monospace; }
.badge { padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.badge-high { background: #D1FAE5; color: #065F46; }
.stat-box { background: white; border: 1px solid #D1D5DB; border-radius: 8px; padding: 0.9rem; text-align: center; }
</style>
"""

# ── Fonctions de persistance ──────────────────────────────────────────────────

def load_inventory() -> pd.DataFrame:
    if os.path.exists(INVENTORY_FILE):
        return pd.read_csv(INVENTORY_FILE, dtype=str)
    return pd.DataFrame(columns=CHAMPS)

def save_inventory(df: pd.DataFrame):
    df.to_csv(INVENTORY_FILE, index=False)

def append_to_inventory(row: dict):
    df = load_inventory()
    new_row = {c: row.get(c, "") for c in CHAMPS}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_inventory(df)

# ── Appel Claude Vision ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un expert en produits de laboratoire. Extrais les informations d'une étiquette.
Renvoie UNIQUEMENT un objet JSON strictement conforme à ce schéma :
{
  "nom_produit": "string", "fabricant": "string", "reference": "string",
  "numero_lot": "string", "numero_cas": "string", "formule": "string",
  "purete": "string", "quantite": "string", "unite": "string",
  "date_peremption": "DD/MM/YYYY", "stockage": "string", "confiance": "high|medium|low",
  "notes": "string"
}"""

def analyser_etiquette(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    client = anthropic.Anthropic(api_key=st.secrets.get("ANTHROPIC_API_KEY", ""))

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
            {"type": "text", "text": "Analyse cette étiquette de produit de laboratoire."}
        ]}]
    )
    raw = message.content[0].text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

# ── Interface UI ──────────────────────────────────────────────────────────────

def render_scanner():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("## 🔬 Scanner d'étiquettes INMED")
    
    tab1, tab2 = st.tabs(["📷 Scanner", "📋 Inventaire"])
    
    with tab1:
        uploaded = st.file_uploader("Importer une photo", type=["jpg", "png"])
        if uploaded:
            img_bytes = uploaded.read()
            st.image(img_bytes, use_container_width=True)
            if st.button("Analyser"):
                with st.spinner("Analyse avec Claude…"):
                    result = analyser_etiquette(img_bytes)
                    st.session_state["last_result"] = result
        
        if "last_result" in st.session_state:
            r = st.session_state["last_result"]
            st.success("Analyse réussie")
            with st.form("validation"):
                nom = st.text_input("Nom", value=r.get("nom_produit", ""))
                if st.form_submit_button("Ajouter à l'inventaire"):
                    r["nom_produit"] = nom
                    r["date_scan"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    append_to_inventory(r)
                    st.rerun()

    with tab2:
        df = load_inventory()
        st.dataframe(df)

if __name__ == "__main__":
    st.set_page_config(page_title="Scanner INMED", layout="wide")
    render_scanner()
