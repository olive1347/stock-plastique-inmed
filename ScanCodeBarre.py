import csv
import os

# Nom du fichier de base de données
FICHIER_DB = 'stock_labo.csv'

def initialiser_db():
    """Crée le fichier CSV s'il n'existe pas avec les colonnes nécessaires."""
    if not os.path.exists(FICHIER_DB):
        with open(FICHIER_DB, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['CodeBarre', 'NomProduit', 'ReferenceFournisseur', 'Fournisseur'])
        print(f"Fichier {FICHIER_DB} créé avec succès.")

def chercher_produit(code_barre):
    """Recherche un produit par son code-barres dans le fichier CSV."""
    with open(FICHIER_DB, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for ligne in reader:
            if ligne['CodeBarre'] == code_barre:
                return ligne
    return None

def ajouter_produit(code_barre):
    """Ajoute un nouveau produit dans le fichier CSV."""
    print(f"\nProduit non trouvé pour le code : {code_barre}")
    nom = input("Nom du produit : ")
    ref = input("Référence fournisseur : ")
    fourn = input("Nom du fournisseur (ex: VWR, Dutscher) : ")
    
    with open(FICHIER_DB, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([code_barre, nom, ref, fourn])
    print("Produit ajouté à la base de données !")

def menu_principal():
    """Boucle principale du programme."""
    initialiser_db()
    print("--- Système de gestion de stock de Labo ---")
    
    while True:
        code = input("\nScannez le code-barres (ou tapez 'q' pour quitter) : ").strip()
        if code.lower() == 'q':
            break
            
        produit = chercher_produit(code)
        
        if produit:
            print(f"\n[TROUVÉ] {produit['NomProduit']}")
            print(f"Référence : {produit['ReferenceFournisseur']}")
            print(f"Fournisseur : {produit['Fournisseur']}")
        else:
            reponse = input("Voulez-vous ajouter ce produit à la base ? (o/n) : ")
            if reponse.lower() == 'o':
                ajouter_produit(code)

if __name__ == "__main__":
    menu_principal()