import streamlit as st
import streamlit.components.v1 as components

st.title("Scanner Code-Barres Debug")

# Composant HTML/JS amélioré
# Ajout de logs pour voir si le navigateur détecte la caméra et le code
scanner_html = """
<div id="reader" style="width: 300px; height: 250px;"></div>
<div id="debug" style="margin-top:10px; color:red; font-size:12px;"></div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    const debug = document.getElementById('debug');
    debug.innerText = "Initialisation...";

    function onScanSuccess(decodedText) {
        debug.innerText = "Succès : " + decodedText;
        // Envoi au parent
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: decodedText
        }, '*');
    }

    function onScanFailure(error) {
        // Ignorer les erreurs de scan continu
    }

    let html5QrcodeScanner = new Html5Qrcode("reader");
    html5QrcodeScanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: 250 },
        onScanSuccess,
        onScanFailure
    ).catch(err => {
        debug.innerText = "Erreur caméra : " + err;
    });
</script>
"""

# Affichage du composant
components.html(scanner_html, height=400)

st.write("Si vous voyez une erreur en rouge au-dessus, c'est la cause du problème.")
st.info("Astuces : 1. Utilisez Chrome. 2. Vérifiez que l'URL est bien 'localhost' ou 'https'. 3. Vérifiez les permissions caméra du navigateur.")
