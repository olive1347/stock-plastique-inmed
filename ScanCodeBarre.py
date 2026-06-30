import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import av
import cv2
from pyzbar.pyzbar import decode

# Configuration de la page
st.set_page_config(page_title="Scanner QR Code", page_icon="📷")

st.title("📷 Scanner QR Code en direct")
st.write("Autorisez l'accès à votre caméra pour commencer le scan.")

# Définition du transformateur vidéo pour traiter les images de la caméra
class QRScannerTransformer(VideoTransformerBase):
    def __init__(self):
        self.result = None

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        
        # Décodage du QR Code via pyzbar
        barcodes = decode(img)
        
        for barcode in barcodes:
            # Récupérer la valeur du QR Code
            decoded_data = barcode.data.decode("utf-8")
            self.result = decoded_data
            
            # Dessiner un rectangle autour du QR Code trouvé
            (x, y, w, h) = barcode.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, decoded_data, (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Initialisation du flux WebRTC
ctx = webrtc_streamer(
    key="qr-scanner",
    video_transformer_factory=QRScannerTransformer,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
)

# Affichage des résultats s'ils sont trouvés
if ctx.video_transformer:
    if ctx.video_transformer.result:
        st.success(f"QR Code détecté : {ctx.video_transformer.result}")
        # Optionnel : bouton pour réinitialiser
        if st.button("Effacer le résultat"):
            ctx.video_transformer.result = None
            st.rerun()

st.info("Astuce : Assurez-vous que votre navigateur autorise l'accès à la caméra pour ce site.")
