import streamlit as st
import base64
import requests
import json

st.set_page_config(page_title="Vision QC - INMED", page_icon="👁️")
st.title("👁️ Contrôle Qualité par Vision - INMED")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

def analyze_image_with_vision(image_bytes):
    """Envoie l'image au modèle vision via Groq avec une gestion d'erreur robuste."""
    if not GROQ_API_KEY:
        return "❌ Erreur : Clé API Groq manquante."

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """Tu es un expert en contrôle qualité pour le matériel de laboratoire plastique.
    Analyse l'image fournie et réponds aux points suivants :
    1. État général : Y a-t-il des déformations, des fissures ou des impuretés visibles ?
    2. Conformité : Le matériel semble-t-il propre et utilisable en milieu stérile ?
    3. Recommandation : Valides-tu l'utilisation de cet article ? (Oui/Non)
    Sois très strict."""

    try:
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.2-11b-vision-instruct", # <-- CHANGEMENT ICI
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                "temperature": 0.2
            },
            timeout=30
        )
        
        # Gestion sécurisée de la réponse API
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            return f"❌ Erreur API Groq : {data['error'].get('message', 'Erreur inconnue')}"
        else:
            return f"❌ Réponse inattendue de l'API : {str(data)}"
            
    except Exception as e:
        return f"❌ Erreur technique : {str(e)}"

st.write("Prenez une photo de l'article pour lancer le contrôle qualité.")
captured_image = st.camera_input("Scanner un article")

if captured_image is not None:
    image_bytes = captured_image.getvalue()
    
    with st.spinner("Analyse en cours par l'IA..."):
        result = analyze_image_with_vision(image_bytes)
        
    st.divider()
    st.subheader("📊 Résultat du contrôle")
    st.write(result)
