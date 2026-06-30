import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import av
import cv2
from pyzbar.pyzbar import decode

# Configuration de la page Streamlit
st.set_page_config(page_title="Scanner de Code Barre", layout="centered")

st.title("📷 Scanner de codes-barres en direct")
st.write("Autorisez l'accès à votre caméra pour commencer le scan.")

# Création d'une variable d'état pour stocker le dernier code détecté
if 'last_code' not in st.session_state:
    st.session_state.last_code = ""

class BarcodeTransformer(VideoTransformerBase):
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        # Conversion du frame en format OpenCV (BGR)
        img = frame.to_ndarray(format="bgr24")
        
        # Décodage des codes-barres
        decoded_objects = decode(img)
        
        for obj in decoded_objects:
            # Récupération de la valeur du code
            code_value = obj.data.decode('utf-8')
            st.session_state.last_code = code_value
            
            # Dessiner un rectangle autour du code détecté
            (x, y, w, h) = obj.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Lancement du flux vidéo
webrtc_streamer(
    key="barcode-scanner",
    video_transformer_factory=BarcodeTransformer,
    rtc_configuration={
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    }
)

# Affichage du résultat détecté
if st.session_state.last_code:
    st.success(f"Dernier code scanné : {st.session_state.last_code}")
else:
    st.info("En attente de détection...")

st.sidebar.markdown("### Instructions")
st.sidebar.write("1. Cliquez sur 'Start'.\n2. Présentez un code-barres devant la caméra.\n3. Le code s'affichera en dessous.")
