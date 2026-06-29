# 2. Extraire le premier bloc {...} trouvé (tolérant aux textes parasites)
    match = re.search(r"\{.*\}", texte, re.DOTALL)
    if not match:
        raise ValueError(f"Aucun objet JSON trouvé dans la réponse :\n{texte[:300]}")
    candidat = match.group(0)

    # 3. Tentative de parsing direct
    try:
        return json.loads(candidat)
    except json.JSONDecodeError:
        pass

    # 4. Nettoyage des caractères de contrôle problématiques et retry
    candidat_clean = re.sub(r'[\x00-\x1f\x7f]', ' ', candidat)
    try:
        return json.loads(candidat_clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalide même après nettoyage : {e}\n---\n{candidat[:500]}")


def extraire_retry_delay(err_msg: str) -> int:
    """Extrait le délai de retry depuis le message d'erreur Gemini (ex: 'retry in 22s')."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", str(err_msg), re.IGNORECASE)
    return int(float(m.group(1))) + 2 if m else 30


def analyser_etiquette(image_bytes: bytes, mime_type: str = "image/jpeg",
                       status_placeholder=None) -> dict:
    """Envoie l'image à Gemini avec compression en amont et retry automatique sur quota 429."""
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise ValueError(
            "Clé API Gemini manquante. "
            "Ajoute GEMINI_API_KEY dans vos secrets Streamlit.\n"
            "Clé gratuite sur : [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)"
        )

    # --- INITIALISATION AVEC LE NOUVEAU SDK GOOGLE-GENAI ---
    client = genai.Client(api_key=api_key)

    # --- ÉTAPE OPTIMISATION ET COMPRESSION DE L'IMAGE ---
    pil_image = Image.open(BytesIO(image_bytes))
    
    # 1. Redimensionner si l'image est trop grande (max 1024px de côté)
    MAX_SIZE = 1024
    if pil_image.width > MAX_SIZE or pil_image.height > MAX_SIZE:
        pil_image.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
    
    # 2. Conversion en RVB si nécessaire
    if pil_image.mode in ("RGBA", "P"):
        pil_image = pil_image.convert("RGB")
        
    # 3. Compression JPEG en mémoire (Quality 80)
    optimized_buffer = BytesIO()
    pil_image.save(optimized_buffer, format="JPEG", quality=80)
    pil_image = Image.open(optimized_buffer)

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            # Appel avec la nouvelle syntaxe du SDK google-genai
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[pil_image, PROMPT_VISION],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                )
            )
            return extraire_json(response.text.strip())

        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "quota" in err.lower() or "resource exhausted" in err.lower()

            if is_quota and attempt < MAX_RETRIES - 1:
                wait = extraire_retry_delay(err)
                if status_placeholder:
                    for remaining in range(wait, 0, -1):
                        status_placeholder.warning(
                            f"⏳ Quota atteint — nouvelle tentative dans **{remaining}s** "
                            f"(essai {attempt + 1}/{MAX_RETRIES - 1})..."
                        )
                        import time; time.sleep(1)
                    status_placeholder.info("🔄 Nouvelle tentative en cours…")
                else:
                    import time; time.sleep(wait)
            else:
                raise


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
        st.image(img_bytes, caption="Image capturée", use_container_width=True)
        st.divider()

        if st.button("🔍 Analyser l'étiquette", type="primary", use_container_width=True):
            status = st.empty()
            with st.spinner("Analyse en cours avec Gemini Vision…"):
                try:
                    result = analyser_etiquette(img_bytes, mime, status_placeholder=status)
                    status.empty()
                    st.session_state["last_result"] = result
                    st.session_state["last_img"] = img_bytes
                except json.JSONDecodeError as e:
                    status.empty()
                    st.error(f"Réponse inattendue du modèle : {e}")
                    return
                except Exception as e:
                    status.empty()
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

    if r.get("notes") and r.get("notes") != "null":
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
            if not nom.strip():
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
