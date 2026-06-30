import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import av
import cv2
from pyzbar.pyzbar import decode

# Configuration de la page
st.set_page_config(page_title="Scanner de Code Barre", layout="centered")

st.title("📷 Scanner de codes-barres")

# Conteneur pour l'affichage dynamique
result_placeholder = st.empty()

class BarcodeTransformer(VideoTransformerBase):
    def __init__(self):
        self.last_detected = None

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        decoded_objects = decode(img)
        
        for obj in decoded_objects:
            code_value = obj.data.decode('utf-8')
            # On met à jour l'état local du transformer
            self.last_detected = code_value
            
            # Dessin
            (x, y, w, h) = obj.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, code_value, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Initialisation du flux
ctx = webrtc_streamer(
    key="barcode-scanner",
    video_transformer_factory=BarcodeTransformer,
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    media_stream_constraints={"video": True, "audio": False}
)

# Boucle pour rafraîchir l'interface avec le résultat
if ctx.video_transformer:
    while True:
        if ctx.video_transformer.last_detected:
            result_placeholder.success(f"Code détecté : {ctx.video_transformer.last_detected}")
        else:
            result_placeholder.info("En attente de détection...")
        
        # Petit délai pour ne pas surcharger le CPU
        import time
        time.sleep(0.5)
