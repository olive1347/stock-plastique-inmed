import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import pytesseract
from pyzbar.pyzbar import decode
import sqlite3
from datetime import datetime
import os

# --- Configuration ---
st.set_page_config(
    page_title="Contrôle Visuel Étiquettes - Labo",
    page_icon="🔬",
    layout="wide"
)

# Chemin vers Tesseract (à adapter)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Linux/Mac
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows

# --- Base de données SQLite ---
DB_NAME = "etiquettes.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etiquettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT,
            text_extracted TEXT,
            barcode TEXT,
            product_name TEXT,
            batch_number TEXT,
            expiry_date TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(image_path, text, barcode, product_name, batch_number, expiry_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO etiquettes (image_path, text_extracted, barcode, product_name, batch_number, expiry_date, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (image_path, text, barcode, product_name, batch_number, expiry_date, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM etiquettes ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# --- Fonctions de traitement ---
def preprocess_image(image):
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return thresh

def extract_text(image):
    img = preprocess_image(image)
    text = pytesseract.image_to_string(img, lang='fra+eng')
    return text.strip()

def extract_barcode(image):
    img = np.array(image)
    barcodes = decode(img)
    return [barcode.data.decode('utf-8') for barcode in barcodes]

def save_image(image, filename_prefix="capture"):
    os.makedirs("uploaded_images", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = f"uploaded_images/{filename_prefix}_{timestamp}.jpg"
    image.save(image_path)
    return image_path

# --- Interface Streamlit ---
def main():
    st.title("🔬 Contrôle Visuel d'Étiquettes - Laboratoire")
    st.markdown("""
        **Fonctionnalités** :
        - **Prendre une photo** avec la webcam ou **uploader une image** (JPG/PNG)
        - Reconnaissance automatique du texte et des codes-barres/QR
        - Stockage en base de données (SQLite)
    """)

    init_db()

    # --- Choix de la méthode d'acquisition ---
    st.header("📷 Acquérir une étiquette")
    method = st.radio(
        "Méthode :",
        ["Prendre une photo avec la webcam", "Uploader une image"],
        horizontal=True
    )

    image = None
    if method == "Prendre une photo avec la webcam":
        # Aperçu de la webcam
        picture = st.camera_input("Positionne l'étiquette devant la caméra")
        if picture:
            image = Image.open(picture)
            st.image(image, caption="Aperçu de l'étiquette", use_column_width=True)

    else:  # Uploader une image
        uploaded_file = st.file_uploader(
            "Choisis une image (JPG/PNG)",
            type=["jpg", "jpeg", "png"]
        )
        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="Image uploadée", use_column_width=True)

    # --- Analyse ---
    if image:
        if st.button("🔍 Analyser l'étiquette", disabled=image is None):
            with st.spinner("Analyse en cours..."):
                # Extraire texte et codes-barres
                text = extract_text(image)
                barcodes = extract_barcode(image)
                barcode = barcodes[0] if barcodes else "Aucun code détecté"

                # Sauvegarder l'image
                image_path = save_image(image, "webcam" if method == "Prendre une photo avec la webcam" else "upload")

                # Afficher les résultats
                st.success("Analyse terminée !")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📄 Texte extrait")
                    st.text_area("Texte", text, height=200)
                with col2:
                    st.subheader("📌 Code-barres/QR")
                    st.code(barcode, language="text")

                # Formulaire pour compléter les métadonnées
                st.subheader("✏️ Compléter les informations")
                with st.form("metadata_form"):
                    product_name = st.text_input("Nom du produit", value="")
                    batch_number = st.text_input("Numéro de lot", value="")
                    expiry_date = st.text_input("Date de péremption (JJ/MM/AAAA)", value="")
                    submitted = st.form_submit_button("Enregistrer en base de données")

                    if submitted:
                        save_to_db(
                            image_path=image_path,
                            text=text,
                            barcode=barcode,
                            product_name=product_name,
                            batch_number=batch_number,
                            expiry_date=expiry_date
                        )
                        st.success("✅ Étiquette enregistrée avec succès !")

    # --- Historique ---
    st.header("📜 Historique des étiquettes")
    history_df = get_history()
    if not history_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            filter_product = st.selectbox(
                "Filtrer par produit",
                ["Tous"] + list(history_df["product_name"].dropna().unique())
            )
        with col2:
            filter_date = st.date_input("Filtrer par date", value=None)

        if filter_product != "Tous":
            history_df = history_df[history_df["product_name"] == filter_product]
        if filter_date:
            history_df["date_only"] = pd.to_datetime(history_df["timestamp"]).dt.date
            history_df = history_df[history_df["date_only"] == filter_date]

        st.dataframe(
            history_df[["timestamp", "product_name", "batch_number", "barcode", "text_extracted"]],
            use_container_width=True,
            height=400
        )

        csv = history_df.to_csv(index=False)
        st.download_button(
            label="📥 Télécharger l'historique (CSV)",
            data=csv,
            file_name="historique_etiquettes.csv",
            mime="text/csv"
        )
    else:
        st.info("Aucune étiquette enregistrée pour l'instant.")

if __name__ == "__main__":
    main()
