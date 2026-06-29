match = re.search(r"\{.*\}", texte, re.DOTALL)
    if not match: raise ValueError("Aucun JSON trouvé")
    return json.loads(match.group(0))

def analyser_etiquette(image_bytes: bytes, mime_type: str, status_placeholder=None) -> dict:
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash") # Mise à jour vers un modèle stable
    
    pil_image = Image.open(BytesIO(image_bytes))
    prompt = "Extrais les informations de l'étiquette en JSON strict selon le schéma fourni."
    
    response = model.generate_content([prompt, pil_image])
    return extraire_json(response.text.strip())

# ── Helpers UI ─────────────────────────────────────────────────────────────────

def badge_confiance(confiance: str) -> str:
    mapping = {"high": ("✅ Haute", "badge-high"), "medium": ("⚠️ Moyenne", "badge-medium"), "low": ("❌ Faible", "badge-low")}
    label, cls = mapping.get(confiance or "low", ("❓ Inconnue", "badge-low"))
    return f'<span class="badge {cls}">{label}</span>'

def champ_card(label: str, value: str):
    if value and value != "None":
        st.markdown(f'<div class="result-card"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)

# ── Onglet Scanner ─────────────────────────────────────────────────────────────

def tab_scanner():
    st.markdown("### 📷 Capturer une étiquette")
    uploaded = st.file_uploader("Importer photo", type=["jpg", "jpeg", "png"])
    if uploaded:
        img_bytes = uploaded.read()
        if st.button("🔍 Analyser"):
            try:
                result = analyser_etiquette(img_bytes, uploaded.type)
                st.session_state["last_result"] = result
            except Exception as e: st.error(f"Erreur : {e}")

    if "last_result" in st.session_state:
        r = st.session_state["last_result"]
        st.markdown(f"#### Résultats " + badge_confiance(r.get("confiance", "low")), unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1: champ_card("Nom", r.get("nom_produit"))
        with col2: champ_card("Lot", r.get("numero_lot"))
        
        if st.button("➕ Ajouter à l'inventaire"):
            append_to_inventory(r)
            st.success("Ajouté !")
            del st.session_state["last_result"]

# ── Point d'entrée ────────────────────────────────────────────────────────────

def render_scanner():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="lab-header"><h1>🔬 Scanner d\'étiquettes INMED</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📷 Scanner", "📋 Inventaire"])
    with tab1: tab_scanner()
    with tab2: st.write("Tableau inventaire ici...")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_scanner()
