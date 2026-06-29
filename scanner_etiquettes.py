"""
scanner_etiquettes.py — Module de scan d'étiquettes pour inventaire labo
Intégrable dans l'app INMED multi-onglets ou en standalone.

Dépendances :
    pip install streamlit google-generativeai pandas pillow

Clé API GRATUITE sur : https://aistudio.google.com/app/apikey
Ajouter dans .streamlit/secrets.toml :
    GEMINI_API_KEY = "AIza..."

Lancer en standalone :
    streamlit run scanner_etiquettes.py

Intégrer dans App.py :
    from scanner_etiquettes import render_scanner
    # puis dans un onglet : render_scanner()
"""

import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
from PIL import Image

# ── Fichier CSV de persistance ────────────────────────────────────────────────
INVENTORY_FILE = "inventaire_labo.csv"

CHAMPS = [
    "date_scan",
    "nom_produit",
    "fabricant",
    "reference",
    "numero_lot",
    "numero_cas",
    "formule",
    "purete",
    "quantite",
    "unite",
    "date_peremption",
    "stockage",
    "emplacement",
    "notes",
]

# ── CSS personnalisé ───────────────────────────────────────────────────────────
CSS = """
<style>
/* Palette lab : blanc cassé, indigo profond, teal */
:root {
    --indigo:  #2D3A8C;
    --teal:    #00A8A8;
    --light:   #F5F7FA;
    --text:    #1A1F36;
    --muted:   #6B7280;
    --border:  #D1D5DB;
    --success: #059669;
    --warn:    #D97706;
}

/* Bandeau de titre */
.lab-header {
    background: linear-gradient(135deg, var(--indigo) 0%, #1a2460 100%);
    color: white;
    padding: 1.2rem 1.6rem;
    border-radius: 10px;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
}
.lab-header h1 { margin: 0; font-size: 1.4rem; font-weight: 700; }
.lab-header p  { margin: 0; font-size: 0.82rem; opacity: 0.75; }

/* Carte résultat IA */
.result-card {
    background: var(--light);
    border: 1px solid var(--border);
    border-left: 4px solid var(--teal);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.result-card .label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin-bottom: 0.15rem;
}
.result-card .value {
    font-size: 0.95rem;
    color: var(--text);
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* Badge confiance */
.badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-high   { background: #D1FAE5; color: #065F46; }
.badge-medium { background: #FEF3C7; color: #92400E; }
.badge-low    { background: #FEE2E2; color: #991B1B; }

/* Compteurs inventaire */
.stat-box {
    background: white;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    text-align: center;
}
.stat-box .num { font-size: 2rem; font-weight: 800; color: var(--indigo); line-height: 1; }
.stat-box .lbl { font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }

/* Séparateur */
.divider { border: none; border-top: 1px solid var(--border); margin: 1.2rem 0; }

/* Champ monospace */
.mono { font-family: 'JetBrains Mono', 'Courier New', monospace; }
</style>
"""


# ── Persistance CSV ────────────────────────────────────────────────────────────

def load_inventory() -> pd.DataFrame:
    if os.path.exists(INVENTORY_FILE):
        try:
            df = pd.read_csv(INVENTORY_FILE, dtype=str)
            # S'assurer que toutes les colonnes existent
            for c in CHAMPS:
                if c not in df.columns:
                    df[c] = ""
            return df[CHAMPS]
        except Exception:
            pass
    return pd.DataFrame(columns=CHAMPS)


def save_inventory(df: pd.DataFrame):
    df.to_csv(INVENTORY_FILE, index=False)


def append_to_inventory(row: dict) -> pd.DataFrame:
    df = load_inventory()
    new_row = {c: row.get(c, "") for c in CHAMPS}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_inventory(df)
    return df


# ── Appel Claude Vision ────────────────────────────────────────────────────────

PROMPT_VISION = """Tu es un expert en produits de laboratoire de recherche scientifique.
On te soumet la photo d'une étiquette de produit chimique ou biologique.
Extrais UNIQUEMENT les informations présentes sur l'étiquette et renvoie un objet JSON strictement conforme au schéma suivant.
Si une valeur est absente ou illisible, utilise null.

Schéma JSON :
{
  "nom_produit":      "string — nom complet du produit",
  "fabricant":        "string — fabricant ou fournisseur",
  "reference":        "string — référence ou code catalogue",
  "numero_lot":       "string — numéro de lot (Lot, Batch, Lot No...)",
  "numero_cas":       "string — numéro CAS si présent (format XXX-XX-X)",
  "formule":          "string — formule chimique brute si présente",
  "purete":           "string — pureté ou grade (ex : ≥99%, HPLC grade...)",
  "quantite":         "string — valeur numérique de la quantité",
  "unite":            "string — unité (mL, L, g, kg, µg, U, mg...)",
  "date_peremption":  "string — date d'expiration au format DD/MM/YYYY si lisible",
  "stockage":         "string — conditions de stockage (température, humidité...)",
  "confiance":        "high | medium | low — ta confiance globale dans l'extraction",
  "notes":            "string — remarques ou avertissements importants (ex: danger, précautions)"
}

Réponds UNIQUEMENT avec l'objet JSON, sans Markdown, sans preamble."""


def analyser_etiquette(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Envoie l'image à Gemini et retourne le JSON parsé."""
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise ValueError(
            "Clé API Gemini manquante. "
            "Ajoute GEMINI_API_KEY dans .streamlit/secrets.toml\n"
            "Clé gratuite sur : https://aistudio.google.com/app/apikey"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",           # gratuit, rapide, vision native
        generation_config=genai.GenerationConfig(
            temperature=0.1,                      # réponses précises et reproductibles
            max_output_tokens=1024,
        ),
    )

    # Convertir bytes → PIL Image pour Gemini
    pil_image = Image.open(BytesIO(image_bytes))

    response = model.generate_content([PROMPT_VISION, pil_image])
    raw = response.text.strip()

    # Retirer éventuels blocs ```json
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ── Helpers UI ─────────────────────────────────────────────────────────────────

def badge_confiance(confiance: str) -> str:
    mapping = {
        "high":   ("✅ Haute",  "badge-high"),
        "medium": ("⚠️ Moyenne", "badge-medium"),
        "low":    ("❌ Faible",  "badge-low"),
    }
    label, cls = mapping.get(confiance or "low", ("❓ Inconnue", "badge-low"))
    return f'<span class="badge {cls}">{label}</span>'


def champ_card(label: str, value: str):
    if value and value != "None":
        st.markdown(
            f"""<div class="result-card">
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                </div>""",
            unsafe_allow_html=True,
        )


# ── Onglet Scanner ─────────────────────────────────────────────────────────────

def tab_scanner():
    st.markdown("### 📷 Capturer une étiquette")

    source = st.radio(
        "Source de l'image",
        ["Caméra", "Importer un fichier"],
        horizontal=True,
        label_visibility="collapsed",
    )

    img_bytes, mime = None, "image/jpeg"

    if source == "Caméra":
        photo = st.camera_input("Pointer vers l'étiquette et prendre la photo")
        if photo:
            img_bytes = photo.getvalue()
    else:
        uploaded = st.file_uploader(
            "Importer une photo d'étiquette",
            type=["jpg", "jpeg", "png", "webp"],
        )
        if uploaded:
            img_bytes = uploaded.read()
            mime = uploaded.type or "image/jpeg"

    if img_bytes:
        st.image(img_bytes, caption="Image capturée", use_container_width=True)
        st.divider()

        if st.button("🔍 Analyser l'étiquette", type="primary", use_container_width=True):
            with st.spinner("Analyse en cours avec Claude Vision…"):
                try:
                    result = analyser_etiquette(img_bytes, mime)
                    st.session_state["last_result"] = result
                    st.session_state["last_img"] = img_bytes
                except json.JSONDecodeError as e:
                    st.error(f"Réponse inattendue du modèle : {e}")
                    return
                except Exception as e:
                    st.error(f"Erreur API : {e}")
                    return

    if "last_result" not in st.session_state:
        return

    r = st.session_state["last_result"]
    confiance = r.get("confiance", "low")

    st.markdown("---")
    st.markdown(
        f"#### Résultats de l'analyse &nbsp;&nbsp;"
        + badge_confiance(confiance),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        champ_card("Nom du produit",    str(r.get("nom_produit") or ""))
        champ_card("Fabricant",         str(r.get("fabricant") or ""))
        champ_card("Référence",         str(r.get("reference") or ""))
        champ_card("Numéro de lot",     str(r.get("numero_lot") or ""))
        champ_card("Numéro CAS",        str(r.get("numero_cas") or ""))
    with col2:
        champ_card("Formule chimique",  str(r.get("formule") or ""))
        champ_card("Pureté / Grade",    str(r.get("purete") or ""))
        champ_card("Quantité",          f"{r.get('quantite', '')} {r.get('unite', '')}".strip())
        champ_card("Date péremption",   str(r.get("date_peremption") or ""))
        champ_card("Stockage",          str(r.get("stockage") or ""))

    if r.get("notes"):
        st.info(f"ℹ️ {r['notes']}")

    # ── Formulaire de validation avant ajout ──────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✏️ Valider et compléter avant d'ajouter à l'inventaire")

    with st.form("form_validation"):
        c1, c2 = st.columns(2)
        with c1:
            nom        = st.text_input("Nom du produit *",    value=r.get("nom_produit") or "")
            fabricant  = st.text_input("Fabricant",           value=r.get("fabricant") or "")
            reference  = st.text_input("Référence / Catalogue", value=r.get("reference") or "")
            lot        = st.text_input("Numéro de lot",       value=r.get("numero_lot") or "")
            cas        = st.text_input("Numéro CAS",          value=r.get("numero_cas") or "")
            formule    = st.text_input("Formule chimique",    value=r.get("formule") or "")
        with c2:
            purete     = st.text_input("Pureté / Grade",      value=r.get("purete") or "")
            quantite   = st.text_input("Quantité",            value=str(r.get("quantite") or ""))
            unite      = st.text_input("Unité",               value=r.get("unite") or "")
            peremption = st.text_input("Date péremption (JJ/MM/AAAA)", value=r.get("date_peremption") or "")
            stockage   = st.text_input("Conditions de stockage", value=r.get("stockage") or "")
            emplacement = st.text_input("Emplacement (armoire, frigo…)", value="")

        notes = st.text_area("Notes / Remarques", value=r.get("notes") or "", height=70)

        submitted = st.form_submit_button(
            "➕ Ajouter à l'inventaire",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not nom.strip():
                st.error("Le nom du produit est obligatoire.")
            else:
                entry = {
                    "date_scan":       datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "nom_produit":     nom.strip(),
                    "fabricant":       fabricant.strip(),
                    "reference":       reference.strip(),
                    "numero_lot":      lot.strip(),
                    "numero_cas":      cas.strip(),
                    "formule":         formule.strip(),
                    "purete":          purete.strip(),
                    "quantite":        quantite.strip(),
                    "unite":           unite.strip(),
                    "date_peremption": peremption.strip(),
                    "stockage":        stockage.strip(),
                    "emplacement":     emplacement.strip(),
                    "notes":           notes.strip(),
                }
                append_to_inventory(entry)
                st.success(f"✅ **{nom}** ajouté à l'inventaire !")
                # Nettoyer pour le prochain scan
                del st.session_state["last_result"]
                if "last_img" in st.session_state:
                    del st.session_state["last_img"]
                st.rerun()


# ── Onglet Inventaire ──────────────────────────────────────────────────────────

def tab_inventaire():
    df = load_inventory()

    # Stats rapides
    n_total   = len(df)
    n_fabrics = df["fabricant"].replace("", pd.NA).dropna().nunique()
    # Produits périmés ou sans date
    n_perime  = 0
    now = datetime.now()
    if "date_peremption" in df.columns:
        for v in df["date_peremption"]:
            try:
                d = datetime.strptime(str(v), "%d/%m/%Y")
                if d < now:
                    n_perime += 1
            except Exception:
                pass

    c1, c2, c3, c4 = st.columns(4)
    for col, num, lbl in [
        (c1, n_total,   "Produits total"),
        (c2, n_fabrics, "Fabricants"),
        (c3, n_perime,  "Périmés"),
        (c4, len(df[df["emplacement"] == ""]) if n_total else 0, "Sans emplacement"),
    ]:
        col.markdown(
            f'<div class="stat-box"><div class="num">{num}</div><div class="lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    if n_total == 0:
        st.info("Inventaire vide — scannez votre premier produit dans l'onglet **Scanner**.")
        return

    # Filtres
    with st.expander("🔍 Filtrer / Rechercher", expanded=False):
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            search = st.text_input("Recherche libre (nom, réf, lot…)", "")
        with fcol2:
            fab_opts = ["Tous"] + sorted(df["fabricant"].replace("", pd.NA).dropna().unique().tolist())
            fab_filter = st.selectbox("Fabricant", fab_opts)
        with fcol3:
            loc_opts = ["Tous"] + sorted(df["emplacement"].replace("", pd.NA).dropna().unique().tolist())
            loc_filter = st.selectbox("Emplacement", loc_opts)

    filtered = df.copy()
    if search:
        mask = filtered.apply(
            lambda row: search.lower() in " ".join(row.astype(str).values).lower(),
            axis=1,
        )
        filtered = filtered[mask]
    if fab_filter != "Tous":
        filtered = filtered[filtered["fabricant"] == fab_filter]
    if loc_filter != "Tous":
        filtered = filtered[filtered["emplacement"] == loc_filter]

    st.markdown(f"**{len(filtered)}** produit(s) affiché(s)")

    # Colonnes à afficher dans le tableau
    DISPLAY_COLS = [
        "date_scan", "nom_produit", "fabricant", "reference",
        "numero_lot", "numero_cas", "quantite", "unite",
        "date_peremption", "stockage", "emplacement",
    ]
    display_cols = [c for c in DISPLAY_COLS if c in filtered.columns]

    st.dataframe(
        filtered[display_cols].reset_index(drop=True),
        use_container_width=True,
        height=400,
        column_config={
            "date_scan":       st.column_config.TextColumn("Date scan", width="small"),
            "nom_produit":     st.column_config.TextColumn("Produit", width="medium"),
            "fabricant":       st.column_config.TextColumn("Fabricant", width="small"),
            "reference":       st.column_config.TextColumn("Référence", width="small"),
            "numero_lot":      st.column_config.TextColumn("Lot", width="small"),
            "numero_cas":      st.column_config.TextColumn("CAS", width="small"),
            "quantite":        st.column_config.TextColumn("Qté", width="small"),
            "unite":           st.column_config.TextColumn("Unité", width="small"),
            "date_peremption": st.column_config.TextColumn("Péremption", width="small"),
            "stockage":        st.column_config.TextColumn("Stockage", width="medium"),
            "emplacement":     st.column_config.TextColumn("Emplacement", width="small"),
        },
    )

    # Export CSV
    csv_bytes = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Exporter en CSV",
        data=csv_bytes,
        file_name=f"inventaire_labo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=False,
    )

    # Suppression d'entrée
    st.markdown("---")
    with st.expander("🗑️ Supprimer une entrée", expanded=False):
        if n_total > 0:
            options = {
                f"{i+1} — {row['nom_produit']} (lot {row['numero_lot']}, {row['date_scan']})": i
                for i, row in df.iterrows()
            }
            chosen_label = st.selectbox("Sélectionner l'entrée à supprimer", list(options.keys()))
            if st.button("Supprimer", type="secondary"):
                idx = options[chosen_label]
                df = df.drop(index=idx).reset_index(drop=True)
                save_inventory(df)
                st.success("Entrée supprimée.")
                st.rerun()


# ── Point d'entrée principal ───────────────────────────────────────────────────

def render_scanner():
    """Appeler cette fonction depuis App.py dans un onglet."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        """<div class="lab-header">
            <div>
                <h1>🔬 Scanner d'étiquettes</h1>
                <p>INMED — Inventaire par vision IA · Propulsé par Gemini Flash</p>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📷 Scanner", "📋 Inventaire"])
    with tab1:
        tab_scanner()
    with tab2:
        tab_inventaire()


# ── Mode standalone ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(
        page_title="Scanner Étiquettes — INMED",
        page_icon="🔬",
        layout="wide",
    )
    render_scanner()
