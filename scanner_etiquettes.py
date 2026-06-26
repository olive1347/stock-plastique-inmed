if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Cherche n'importe quelle structure avec des accolades { ... } ou [ ... ]
    m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None

# ── Appel Groq Vision ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un expert en produits de laboratoire de recherche scientifique.
On te soumet la photo d'une étiquette de produit chimique ou biologique.
Extrais UNIQUEMENT les informations présentes sur l'étiquette et renvoie un objet JSON strictement conforme au schéma suivant.
Si une valeur est absente ou illisible, utilise null.
Tu dois répondre UNIQUEMENT avec l'objet JSON enveloppé dans des blocs de code ```json ... ```, sans aucun texte d'introduction ni conclusion.

Schéma JSON attendu :
{
  "nom_produit": "string — nom complet du produit",
  "fabricant": "string — fabricant ou fournisseur",
  "reference": "string — référence ou code catalogue",
  "numero_lot": "string — numéro de lot (Lot, Batch, Lot No...)",
  "numero_cas": "string — numéro CAS si présent (format XXX-XX-X)",
  "formule": "string — formule chimique brute si présente",
  "purete": "string — pureté ou grade (ex : ≥99%, HPLC grade...)",
  "quantite": "string — valeur numérique de la quantité",
  "unite": "string — unité (mL, L, g, kg, µg, U, mg...)",
  "date_peremption": "string — date d'expiration au format DD/MM/YYYY si lisible",
  "stockage": "string — conditions de stockage (température, humidité...)",
  "confiance": "high | medium | low — ta confiance globale dans l'extraction",
  "notes": "string — remarques ou avertissements importants (ex: danger, précautions)"
}"""

def analyser_etiquette(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Envoie l'image à Groq (Llama 3.2 Vision) et retourne le JSON parsé."""
    api_key = st.secrets.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("La clé API 'GROQ_API_KEY' est manquante dans vos Secrets Streamlit.")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.2-11b-vision-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": SYSTEM_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}}
                        ]
                    }
                ],
                "temperature": 0.1
            },
            timeout=30
        )
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            raw_text = data["choices"][0]["message"]["content"]
            parsed_json = extract_json(raw_text)
            if parsed_json:
                return parsed_json
            raise ValueError(f"Le format JSON n'a pas pu être extrait de la réponse de l'IA.\nRéponse brute : {raw_text}")
        elif "error" in data:
            raise ValueError(data["error"].get("message", "Erreur renvoyée par Groq."))
        else:
            raise ValueError("Réponse invalide reçue de l'API Groq.")
            
    except Exception as e:
        raise RuntimeError(f"Erreur de communication : {str(e)}")

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
    if value and value != "None" and value != "null":
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
        st.image(img_bytes, caption="Image sélectionnée", use_container_width=True)
        st.divider()

        if st.button("🔍 Analyser l'étiquette", type="primary", use_container_width=True):
            with st.spinner("Analyse de l'étiquette en cours avec Llama 3.2 Vision (Groq)…"):
                try:
                    result = analyser_etiquette(img_bytes, mime)
                    st.session_state["last_result"] = result
                    st.session_state["last_img"] = img_bytes
                except Exception as e:
                    st.error(f"❌ {str(e)}")
                    return

    if "last_result" not in st.session_state:
        return

    r = st.session_state["last_result"]
    confiance = r.get("confiance", "low")

    st.markdown("---")
    st.markdown(
        f"#### Résultats de l'analyse &nbsp;&nbsp;" + badge_confiance(confiance),
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
        
        qty_val = r.get('quantite') or ""
        unit_val = r.get('unite') or ""
        qty_str = f"{qty_val} {unit_val}".strip()
        champ_card("Quantité",          qty_str if qty_str else "N/A")
        
        champ_card("Date péremption",   str(r.get("date_peremption") or ""))
        champ_card("Stockage",          str(r.get("stockage") or ""))

    if r.get("notes") and r.get("notes") != "null" and r.get("notes") != "None":
        st.info(f"ℹ️ {r['notes']}")

    # ── Formulaire de validation avant ajout ──────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✏️ Valider et compléter avant d'ajouter à l'inventaire")

    with st.form("form_validation"):
        c1, c2 = st.columns(2)
        with c1:
            nom        = st.text_input("Nom du produit *",     value=r.get("nom_produit") or "")
            fabricant  = st.text_input("Fabricant",            value=r.get("fabricant") or "")
            reference  = st.text_input("Référence / Catalogue", value=r.get("reference") or "")
            lot        = st.text_input("Numéro de lot",        value=r.get("numero_lot") or "")
            cas        = st.text_input("Numéro CAS",           value=r.get("numero_cas") or "")
            formule    = st.text_input("Formule chimique",     value=r.get("formule") or "")
        with c2:
            purete     = st.text_input("Pureté / Grade",       value=r.get("purete") or "")
            quantite   = st.text_input("Quantité",             value=str(r.get("quantite") or ""))
            unite      = st.text_input("Unité",                value=r.get("unite") or "")
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
            if not nom.strip() or nom.lower() == "null" or nom.lower() == "none":
                st.error("Le nom du produit est obligatoire.")
            else:
                entry = {
                    "date_scan":       datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "nom_produit":      nom.strip(),
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
                if "last_result" in st.session_state:
                    del st.session_state["last_result"]
                if "last_img" in st.session_state:
                    del st.session_state["last_img"]
                st.rerun()


# ── Onglet Inventaire ──────────────────────────────────────────────────────────

def tab_inventaire():
    df = load_inventory()

    # Stats rapides
    n_total   = len(df)
    n_fabrics = df["fabricant"].replace("", pd.NA).replace("null", pd.NA).dropna().nunique()
    n_perime  = 0
    now = datetime.now()
    if "date_peremption" in df.columns:
        for v in df["date_peremption"]:
            try:
                d = datetime.strptime(str(v).strip(), "%d/%m/%Y")
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
            fab_opts = ["Tous"] + sorted(df["fabricant"].replace("", pd.NA).replace("null", pd.NA).dropna().unique().tolist())
            fab_filter = st.selectbox("Fabricant", fab_opts)
        with fcol3:
            loc_opts = ["Tous"] + sorted(df["emplacement"].replace("", pd.NA).replace("null", pd.NA).dropna().unique().tolist())
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
                <p>INMED — Inventaire par vision IA · Propulsé par Groq (Llama 3.2 Vision)</p>
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
