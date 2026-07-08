"""Map Flask app template for rebuild trials."""

MAP_FLASK_APP = '''"""Minimal rebuild scaffold for the analyzed map project."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
ROAD_BY_ZOOM = [(8, {'motorway', 'trunk', 'primary'}), (13, {'primary', 'secondary', 'tertiary', 'residential'}), (99, {'service', 'residential'})]

def load_json(path: str, default: object) -> object:
    target = BASE_DIR / path
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding='utf-8'))

def parse_bbox(raw_bbox: str | None):
    if not raw_bbox:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = [float(value) for value in raw_bbox.split(',')]
    except ValueError:
        return None
    if min_lon > max_lon or min_lat > max_lat:
        return None
    return min_lon, min_lat, max_lon, max_lat

def point_in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

def allowed_highways_for_zoom(zoom: int):
    for max_zoom, highways in ROAD_BY_ZOOM:
        if zoom <= max_zoom:
            return highways
    return ROAD_BY_ZOOM[-1][1]

def feature_collection(name: str) -> dict:
    return dict(load_json(name, {'type': 'FeatureCollection', 'features': []}))

def incident_data() -> dict:
    return dict(load_json('incidents.json', {'dates': [], 'groups': [], 'events': [], 'stats': {}}))

def node_items() -> list[dict]:
    value = load_json('kursk_nodes.json', [])
    return value if isinstance(value, list) else []

@app.route('/')
def index():
    return '<main data-api="/get_vector_map"><h1>map_x</h1><input name="search"><section id="map"></section><section id="incidents"></section></main>'

@app.route('/get_vector_map')
def get_vector_map():
    data = feature_collection('kursk_vector_map.json')
    bbox = parse_bbox(request.args.get('bbox'))
    zoom = int(request.args.get('zoom') or 10)
    return jsonify(type=data.get('type'), features=data.get('features', [])[:12000], bbox=bbox, zoom=zoom)

@app.route('/incident_meta')
def incident_meta():
    data = incident_data()
    return jsonify(dates=data.get('dates', []), groups=data.get('groups', []), stats=data.get('stats', {}))

@app.route('/import_indoc/start', methods=['POST'])
def import_indoc_start():
    return jsonify(running=False, accepted=True, message='Import execution is intentionally disabled in map_x MVP.')

@app.route('/import_indoc/status')
def import_indoc_status():
    return jsonify(running=False, ok=None, message='Import has not been run in map_x.', started_at='', finished_at='', output='')

@app.route('/get_incidents')
def get_incidents():
    data = incident_data()
    features = data.get('features') or data.get('events', [])
    return jsonify(type='FeatureCollection', features=features)

@app.route('/branches_atms')
def branches_atms():
    return jsonify(feature_collection('branches_atms.json'))

@app.route('/unmatched_incidents')
def unmatched_incidents():
    data = incident_data()
    events = [item for item in data.get('events', []) if not item.get('matched')]
    return jsonify(count=len(events), events=events)

@app.route('/export_incidents')
def export_incidents():
    return jsonify(incident_data())

@app.route('/search')
def search():
    query = str(request.args.get('q') or '').strip().lower()
    rows = []
    for item in node_items():
        name = str(item.get('name') or '')
        if query and query not in name.lower():
            continue
        rows.append({'name': name, 'type': item.get('type'), 'lat': item.get('lat'), 'lon': item.get('lon')})
    return jsonify(rows[:50])

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
'''
