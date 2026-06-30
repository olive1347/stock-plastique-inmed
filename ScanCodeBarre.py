import streamlit as st

# Initialisation de l'historique dans la session
if 'history' not in st.session_state:
    st.session_state.history = []

st.set_page_config(page_title="Scanner Pro", page_icon="📷")
st.title("📷 Scanner de Codes")

# Zone de scan (utilisation du widget natif pour une stabilité maximale sur Cloud)
img_file = st.camera_input("Placez le code devant la caméra")

if img_file:
    # Simulation de traitement (Remplacez par votre logique pyzbar)
    scanned_data = "CODE_123456789" 
    
    if scanned_data not in st.session_state.history:
        st.session_state.history.append(scanned_data)
        st.toast("Code scanné avec succès !", icon="✅")

# Affichage de l'historique sous forme de liste propre
if st.session_state.history:
    st.subheader("Historique des scans")
    for i, code in enumerate(reversed(st.session_state.history)):
        st.write(f"{i+1}. 📦 {code}")
        
    if st.button("Effacer l'historique"):
        st.session_state.history = []
        st.rerun()
else:
    st.info("Aucun scan pour le moment.")
