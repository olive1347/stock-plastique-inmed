"""
scanner_etiquettes.py — Module de scan d'étiquettes pour inventaire labo
Intégrable dans l'app INMED multi-onglets ou en standalone.

Dépendances dans requirements.txt :
    streamlit
    google-generativeai
    pandas
    pillow
    openpyxl

Clé API GRATUITE sur : https://aistudio.google.com/app/apikey
Ajouter dans Streamlit Cloud Secrets :
    GEMINI_API_KEY = "AIza..."
"""

import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import os
import re
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


# ── Extraction & Appel Gemini Vision ───────────────────────────────────────────

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


def extraire_json(texte: str) -> dict:
    """
    Extrait robustement un objet JSON depuis une réponse texte,
    même si le modèle a ajouté du texte autour ou a mal échappé des caractères.
    """
    # 1. Retirer les blocs Markdown ```json ...
