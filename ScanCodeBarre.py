import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import av
import cv2
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Scanner de Code Barre", layout="centered")
st.title("📷 Scanner de codes-barres")

result_placeholder = st.empty()

class BarcodeTransformer(VideoTransformerBase):
    def __init__(self):
        self.last_detected = None

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        decoded_objects = decode(img)
        
        for obj in decoded_objects:
            code_value = obj.data.decode('utf-8')
            self.last_detected = code_value
            
            (x, y, w, h) = obj.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, code_value, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
        return av.VideoFrame.from_ndarray(img, format="bgr24")

ctx = webrtc_streamer(
    key="barcode-scanner",
    video_transformer_factory=BarcodeTransformer,
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    media_stream_constraints={"video": True, "audio": False}
)

# Correction : Vérification sécurisée de l'existence de l'objet et de l'attribut
if ctx and hasattr(ctx, "video_transformer") and ctx.video_transformer:
    # On accède à la valeur détectée
    detected = ctx.video_transformer.last_detected
    if detected:
        result_placeholder.success(f"Code détecté : {detected}")
    else:
        result_placeholder.info("En attente de détection...")
else:
    result_placeholder.warning("Veuillez activer la caméra pour scanner.")
