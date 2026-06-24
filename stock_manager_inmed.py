import streamlit as st
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
FILE_PATH = "stock-plastique.xlsx"
SHEET_NAME = "Feuil1"

# --- FONCTIONS ---
@st.cache_data
def load_data():
    """Charge et nettoie le fichier Excel."""
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME)
    df = df.dropna(how="all")  # Supprime les lignes vides
    df = df.dropna(subset=["Designation"])  # Supprime les lignes sans designation
    df["Prix"] = pd.to_numeric(df["Prix"], errors="coerce")  # Convertit les prix en float
    return df

def send_email(panier_df, email_utilisateur):
    """Envoie un récapitulatif de commande par email (optionnel)."""
    try:
        # Configurer votre serveur SMTP (ex: Gmail)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "votre-email@gmail.com"  # À remplacer
        smtp_password = "votre-mot-de-passe-app"  # Utilisez un "App Password" pour Gmail

        # Créer l'email
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email_utilisateur
        msg["Subject"] = f"Commande de matériel - {datetime.now().strftime('%d/%m/%Y')}"

        # Corps de l'email
        body = f"""
        Bonjour,

        Voici le récapitulatif de votre commande :

        {panier_df.to_html(index=False)}

        Total : {panier_df["Total"].sum():.2f} €

        Cordialement,
        L'équipe de l'Institut
        """
        msg.attach(MIMEText(body, "html"))

        # Envoyer
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'envoi de l'email : {e}")
        return False

# --- INTERFACE STREAMLIT ---
def main():
    st.set_page_config(page_title="Commande Matériel - INMED", layout="wide", page_icon="🧪")
    st.title("🧪 Commande de matériel - INMED")
    st.markdown("Sélectionnez les articles à commander ci-dessous.")

    # Charger les données
    df = load_data()

    # Initialiser le panier
    if "panier" not in st.session_state:
        st.session_state.panier = []

    # --- SIDEBAR (Filtres) ---
    with st.sidebar:
        st.header("🔍 Filtres")
        st.image("https://via.placeholder.com/150x50?text=INMED", use_container_width=True)  # Remplacez par votre logo
        categories = ["Toutes"] + sorted(df["Catégories"].dropna().unique().tolist())
        selected_category = st.selectbox("Catégorie", categories)

        fabricants = ["Tous"] + sorted(df["Fabricant"].dropna().unique().tolist())
        selected_fabricant = st.selectbox("Fabricant", fabricants)

        if not df["Prix"].isna().all():
            min_price, max_price = float(df["Prix"].min()), float(df["Prix"].max())
            price_range = st.slider(
                "Prix (€)",
                min_value=min_price,
                max_value=max_price,
                value=(min_price, max_price)
            )

    # Appliquer les filtres
    filtered_df = df.copy()
    if selected_category != "Toutes":
        filtered_df = filtered_df[filtered_df["Catégories"] == selected_category]
    if selected_fabricant != "Tous":
        filtered_df = filtered_df[filtered_df["Fabricant"] == selected_fabricant]
    if not filtered_df["Prix"].isna().all():
        filtered_df = filtered_df[
            (filtered_df["Prix"] >= price_range[0]) &
            (filtered_df["Prix"] <= price_range[1])
        ]

    # --- AFFICHAGE DES ARTICLES ---
    st.subheader(f"📦 Catalogue ({len(filtered_df)} articles)")
    for _, row in filtered_df.iterrows():
        with st.expander(f"**{row['Designation']}** | {row['Fabricant']}"):
            cols = st.columns([4, 1, 1, 1])
            with cols[0]:
                st.write(f"**Catégorie** : {row['Catégories']}")
                st.write(f"**Informations** : {row['Informations']}")
                if pd.notna(row["Ref fabricant"]):
                    st.write(f"**Réf. Fabricant** : {row['Ref fabricant']}")
                if pd.notna(row["Ref UGAP"]):
                    st.write(f"**Réf. UGAP** : {row['Ref UGAP']}")
            with cols[1]:
                prix = f"{row['Prix']:.2f} €" if pd.notna(row["Prix"]) else "Prix sur demande"
                st.write(f"**Prix** : {prix}")
            with cols[2]:
                quantity = st.number_input(
                    "Quantité",
                    min_value=0,
                    max_value=1000,
                    key=f"qte_{row['Designation']}_{row['Fabricant']}",
                    label_visibility="collapsed"
                )
            with cols[3]:
                if st.button("➕ Ajouter", key=f"btn_{row['Designation']}_{row['Fabricant']}"):
                    if quantity > 0:
                        prix_unitaire = row["Prix"] if pd.notna(row["Prix"]) else 0
                        st.session_state.panier.append({
                            "Designation": row["Designation"],
                            "Fabricant": row["Fabricant"],
                            "Prix": prix_unitaire,
                            "Quantité": quantity,
                            "Total": prix_unitaire * quantity,
                            "Ref fabricant": row["Ref fabricant"],
                            "Informations": row["Informations"]
                        })
                        st.success(f"✅ {quantity} x {row['Designation']} ajouté au panier")
                    else:
                        st.warning("Veuillez indiquer une quantité > 0")

    # --- PANIER ---
    st.subheader("🛒 Votre panier")
    if not st.session_state.panier:
        st.info("Votre panier est vide.")
    else:
        panier_df = pd.DataFrame(st.session_state.panier)
        if not panier_df.empty:
            # Calculer le total
            panier_df["Total"] = panier_df["Prix"] * panier_df["Quantité"]
            st.dataframe(
                panier_df[["Designation", "Fabricant", "Quantité", "Prix", "Total"]],
                hide_index=True,
                use_container_width=True
            )
            total = panier_df["Total"].sum()
            st.metric("**Total à payer**", f"{total:.2f} €")

            # Boutons d'action
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🗑 Vider le panier", use_container_width=True):
                    st.session_state.panier = []
                    st.rerun()
            with col2:
                csv = panier_df.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger (CSV)",
                    data=csv,
                    file_name=f"commande_inmed_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col3:
                excel_buffer = panier_df.to_excel(index=False, engine="openpyxl")
                st.download_button(
                    label="📥 Télécharger (Excel)",
                    data=excel_buffer,
                    file_name=f"commande_inmed_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            # Validation de la commande
            st.divider()
            st.subheader("📝 Valider la commande")
            with st.form("validation_form"):
                nom = st.text_input("Nom *", placeholder="Votre nom")
                email = st.text_input("Email *", placeholder="Votre email @inmed.fr")
                service = st.text_input("Service/Équipe", placeholder="Ex: Biologie")
                commentaires = st.text_area("Commentaires", placeholder="Ex: Urgent, à livrer avant le...")
                submitted = st.form_submit_button("✅ Valider la commande")

                if submitted:
                    if not nom or not email:
                        st.error("Veuillez remplir les champs obligatoires (Nom et Email).")
                    else:
                        # Ajouter les infos au panier
                        panier_df["Nom"] = nom
                        panier_df["Email"] = email
                        panier_df["Service"] = service
                        panier_df["Date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        panier_df["Commentaires"] = commentaires

                        # Envoyer un email (optionnel)
                        if st.toggle("Envoyer un récapitulatif par email", value=False):
                            if send_email(panier_df, email):
                                st.success("✅ Commande validée et email envoyé !")
                            else:
                                st.warning("⚠️ Commande validée, mais l'email n'a pas pu être envoyé.")
                        else:
                            st.success("✅ Commande validée !")

                        # Vider le panier
                        st.session_state.panier = []
                        st.rerun()

if __name__ == "__main__":
    main()
