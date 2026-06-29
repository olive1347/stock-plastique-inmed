# Extraction du bloc JSON principal
    match = re.search(r"\{.*\}", texte, re.DOTALL)
    if not match:
        raise ValueError("Aucun objet JSON trouvé.")
    return json.loads(match.group(0))

def analyser_etiquette(image_bytes: bytes) -> dict:
    """Analyse l'image avec le SDK google-genai."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Clé API manquante dans les secrets Streamlit.")
        return {}

    client = genai.Client(api_key=api_key)
    pil_image = Image.open(BytesIO(image_bytes))

    # Appel au modèle
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[pil_image, "Extrais les infos de cette étiquette labo en JSON."],
    )
    return extraire_json(response.text)

# ── Interface principale ─────────────────────────────────────────────────────

def main():
    st.title("🔬 Scanner d'Étiquettes INMED")
    
    uploaded_file = st.file_uploader("Choisir une photo", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="Image à analyser")
        if st.button("Analyser"):
            with st.spinner("Analyse en cours..."):
                try:
                    resultat = analyser_etiquette(uploaded_file.getvalue())
                    st.write("Résultat de l'analyse :", resultat)
                except Exception as e:
                    st.error(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
