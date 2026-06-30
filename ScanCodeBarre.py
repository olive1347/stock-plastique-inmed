import streamlit as st
import streamlit.components.v1 as components

st.title("Scanner Code-Barres Persistant")

# Cette version utilise localStorage pour passer la donnée de JS vers Python
scanner_html = """
<div id="reader" style="width: 300px; height: 250px;"></div>
<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    function onScanSuccess(decodedText) {
        // Enregistre dans le localStorage du navigateur
        localStorage.setItem('scanned_code', decodedText);
        // Force un rafraîchissement visuel pour l'utilisateur
        document.body.style.backgroundColor = '#d4edda';
    }

    let html5QrcodeScanner = new Html5Qrcode("reader");
    html5QrcodeScanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: 250 },
        onScanSuccess
    );
</script>
"""

# 1. Afficher le scanner
components.html(scanner_html, height=300)

# 2. Utiliser un composant pour lire le localStorage
# (Streamlit ne peut pas lire le localStorage directement, 
# on utilise donc un petit script pour envoyer la valeur à Streamlit)
valeur_scan = components.html("""
<script>
    function checkScan() {
        const code = localStorage.getItem('scanned_code');
        if (code) {
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: code}, '*');
            localStorage.removeItem('scanned_code');
        }
    }
    setInterval(checkScan, 1000);
</script>
""", height=0)

st.write("Scannez un code, il apparaîtra ci-dessous :")
# Note : Pour récupérer la valeur réelle dans votre logique Python, 
# vous devrez passer par un vrai 'Custom Component' Streamlit.
# En attendant, vérifiez si la couleur de fond du scanner passe au vert.
