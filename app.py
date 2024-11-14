from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import osmnx as ox
import networkx as nx
import requests
import time
import os
from models import init_db, ajouter_utilisateur, recuperer_utilisateurs, supprimer_utilisateur_bd, verifier_login  # Import des fonctions DB


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clé secrète pour les sessions

# Initialiser la base de données et ajouter les personnages des Simpsons
init_db()

# Route pour la page de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        utilisateur = verifier_login(email, password)
        
        if utilisateur:
            session['user_id'] = utilisateur[0]
            session['user_name'] = utilisateur[1]
            return redirect(url_for('index'))
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

# Route pour déconnecter l'utilisateur
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Protection de la route
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Formulaire pour ajouter un utilisateur
@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = request.form['password']
        password_confirm = request.form['password_confirm']  # Récupération du second mot de passe

        # Vérification que les deux mots de passe correspondent
        if password != password_confirm:
            flash('Les mots de passe ne correspondent pas', 'danger')
            return redirect(url_for('add_user'))

        # Ajouter l'utilisateur si les mots de passe correspondent
        ajouter_utilisateur(nom, email, password)
        flash('Utilisateur ajouté avec succès', 'success')
        return redirect(url_for('list_users'))

    return render_template('add_user.html')


# Route pour lister les utilisateurs
@app.route('/users')
@login_required
def list_users():
    utilisateurs = recuperer_utilisateurs()
    return render_template('list_users.html', utilisateurs=utilisateurs)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    supprimer_utilisateur_bd(user_id)  # Appel à la fonction dans models.py
    flash('Utilisateur supprimé avec succès.', 'success')
    return redirect(url_for('list_users'))



# URL de l'API JCDecaux
API_URL = 'https://api.jcdecaux.com/vls/v1/stations?contract=nancy&apiKey=3993633e26d5c2fef3ff02b5273e99e26ffed693'

# Seuils pour définir une station surchargée ou sous-alimentée
SEUIL_SURCHARGE = 0.25
SEUIL_SOUS_ALIMENTE = 0.25

# Charger les graphes depuis les fichiers .graphml
G_cyclable = ox.load_graphml(filepath='graph_cyclable.graphml')
G_drive = ox.load_graphml(filepath='graph_drive.graphml')

# Variables pour stocker les stations et l'heure du dernier appel
stations_cache = {
    'surcharges': [],
    'sous_alimentees': [],
    'normales': []
}
last_fetch_time = 0
CACHE_DURATION = 60  # Durée de validité du cache en secondes (60s)

# Fonction pour récupérer les données de l'API JCDecaux et les classer
def recuperer_stations():
    global stations_cache, last_fetch_time

    # Si le cache est encore valide, renvoyer les données en cache
    if time.time() - last_fetch_time < CACHE_DURATION:
        return stations_cache['surcharges'], stations_cache['sous_alimentees'], stations_cache['normales']

    # Sinon, récupérer de nouvelles données depuis l'API
    response = requests.get(API_URL)
    stations = response.json()

    stations_surcharges = []
    stations_sous_alimentees = []
    stations_normales = []

    for station in stations:
        id_ = station['number']
        name = station['name']
        lat = station['position']['lat']
        lon = station['position']['lng']
        available_bikes = station['available_bikes']
        available_bike_stands = station['available_bike_stands']
        bike_stands = station['bike_stands']

        if available_bike_stands / bike_stands < SEUIL_SURCHARGE:
            stations_surcharges.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))
        elif available_bikes / bike_stands < SEUIL_SOUS_ALIMENTE:
            stations_sous_alimentees.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))
        else:
            stations_normales.append((id_, name, lat, lon, available_bikes, available_bike_stands, bike_stands))

    # Mettre à jour le cache et l'heure de l'appel
    stations_cache['surcharges'] = stations_surcharges
    stations_cache['sous_alimentees'] = stations_sous_alimentees
    stations_cache['normales'] = stations_normales
    last_fetch_time = time.time()

    return stations_surcharges, stations_sous_alimentees, stations_normales

# Route pour afficher la page principale avec la carte
@app.route('/')
@login_required
def index():
    stations_surcharges, stations_sous_alimentees, stations_normales = recuperer_stations()
    return render_template('index.html',
                           stations_surcharges=stations_surcharges,
                           stations_sous_alimentees=stations_sous_alimentees,
                           stations_normales=stations_normales)

# API pour récupérer les stations de vélos au format JSON (utile pour AJAX)
@app.route('/api/stations')
@login_required
def api_stations():
    stations_surcharges, stations_sous_alimentees, stations_normales = recuperer_stations()

    data = {
        'surcharges': [{'id': s[0], 'name': s[1], 'lat': s[2], 'lon': s[3], 'available_bikes': s[4], 'available_bike_stands': s[5]} for s in stations_surcharges],
        'sous_alimentees': [{'id': s[0], 'name': s[1], 'lat': s[2], 'lon': s[3], 'available_bikes': s[4], 'available_bike_stands': s[5]} for s in stations_sous_alimentees],
        'normales': [{'id': s[0], 'name': s[1], 'lat': s[2], 'lon': s[3], 'available_bikes': s[4], 'available_bike_stands': s[5]} for s in stations_normales]
    }

    return jsonify(data)

# API pour calculer l'itinéraire
@app.route('/api/itineraire/<float:lat1>/<float:lon1>/<float:lat2>/<float:lon2>', methods=['POST'])
@login_required
def calculer_itineraire(lat1, lon1, lat2, lon2):
    data = request.get_json()
    mode_deplacement = data.get('mode')

    # Sélectionner le graphe en fonction du mode de déplacement
    if mode_deplacement == 'velo':
        G = G_cyclable
    elif mode_deplacement == 'camionette':
        G = G_drive
    else:
        return jsonify({"error": "Mode de déplacement inconnu"}), 400

    # Récupérer les nœuds les plus proches des deux points
    station_surchargee_node = ox.distance.nearest_nodes(G, lon1, lat1)
    station_sous_alimentee_node = ox.distance.nearest_nodes(G, lon2, lat2)

    try:
        # Calculer le plus court chemin
        chemin = nx.shortest_path(G, station_surchargee_node, station_sous_alimentee_node, weight='length')
        distance = nx.shortest_path_length(G, station_surchargee_node, station_sous_alimentee_node, weight='length')

        # Créer des instructions de base pour chaque étape
        instructions = [f"Continuez vers le nœud {node}" for node in chemin]

        # Retourner les coordonnées des points du chemin
        chemin_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in chemin]
        return jsonify({"chemin": chemin_coords, "distance": distance, "instructions": instructions})
    except nx.NetworkXNoPath:
        return jsonify({"error": "Pas de chemin trouvé"}), 400


if __name__ == '__main__':
    app.run(debug=True)
