import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# Initialisation de la base de données
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Création de la table des utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')

    # Ajouter les personnages des Simpsons avec un mot de passe 'admin' hashé
    utilisateurs_simpsons = [
        ("Homer Simpson", "homer@simpsons.com"),
        ("Marge Simpson", "marge@simpsons.com"),
        ("Bart Simpson", "bart@simpsons.com"),
        ("Lisa Simpson", "lisa@simpsons.com"),
        ("Maggie Simpson", "maggie@simpsons.com")
    ]
    
    for nom, email in utilisateurs_simpsons:
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        if not cursor.fetchone():
            hash_password = generate_password_hash("admin")
            cursor.execute('INSERT INTO users (nom, email, password) VALUES (?, ?, ?)', (nom, email, hash_password))

    conn.commit()
    conn.close()

# Fonction pour ajouter un utilisateur avec un mot de passe hashé
def ajouter_utilisateur(nom, email, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    hash_password = generate_password_hash(password)  # Hashage du mot de passe
    cursor.execute('INSERT INTO users (nom, email, password) VALUES (?, ?, ?)', (nom, email, hash_password))
    conn.commit()
    conn.close()


# Fonction pour récupérer les utilisateurs
def recuperer_utilisateurs():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    utilisateurs = cursor.fetchall()
    conn.close()
    return utilisateurs


# Supprimer un utilisateur
def supprimer_utilisateur_bd(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()



# Fonction pour vérifier le login
def verifier_login(email, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    utilisateur = cursor.fetchone()
    conn.close()

    if utilisateur and check_password_hash(utilisateur[3], password):
        return utilisateur
    return None
