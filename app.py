from flask import Flask, render_template, jsonify, request
import osmnx as ox
import networkx as nx
import requests
import time

app = Flask(__name__)

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
def index():
    stations_surcharges, stations_sous_alimentees, stations_normales = recuperer_stations()
    return render_template('index.html',
                           stations_surcharges=stations_surcharges,
                           stations_sous_alimentees=stations_sous_alimentees,
                           stations_normales=stations_normales)

# API pour récupérer les stations de vélos au format JSON (utile pour AJAX)
@app.route('/api/stations')
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
