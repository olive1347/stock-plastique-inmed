import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os

# Fichier de données
FICHIER_DB = 'stock_labo.csv'
if not os.path.exists(FICHIER_DB):
    pd.DataFrame(columns=['CodeBarre', 'Nom', 'Ref']).to_csv(FICHIER_DB, index=False)

st.set_page_config(page_title="Scanner Web", layout="centered")

st.title("📷 Scanner Code-Barres")

# Le code HTML/JS qui gère la caméra et le décodage
scanner_html = """
<div id="reader" style="width: 100%; border: 1px solid #ccc; border-radius: 8px;"></div>
<div id="result" style="margin-top: 10px; font-weight: bold; color: green;"></div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    function onScanSuccess(decodedText, decodedResult) {
        document.getElementById('result').innerText = "Code détecté : " + decodedText;
        // Envoie le code vers Streamlit
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: decodedText
        }, '*');
    }
    
    let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""

# Affichage du composant caméra
components.html(scanner_html, height=450)

# Récupération du résultat via un paramètre de session ou entrée
# Note : Pour que cela soit fluide, on utilise une saisie cachée
code = st.text_input("Code scanné (automatique) :", key="scanner_input")

if code:
    df = pd.read_csv(FICHIER_DB)
    produit = df[df['CodeBarre'].astype(str) == code]
    
    if not produit.empty:
        st.success("Produit trouvé :")
        st.table(produit)
    else:
        st.warning("Produit inconnu.")
