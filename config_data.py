# config_data.py
# Configuration des simulateurs
SIMULATORS = {
    "TWR": {"positions": 4, "type": "fixed", "mode": "Aérodrome"},
    "RADAR_1": {"positions": 4, "type": "flexible", "mode": "Approche Radar"},
    "RADAR_2": {"positions": 2, "type": "flexible", "mode": "En-route Radar"}
}

# Liste des instructeurs
INSTRUCTORS = [
    {"id": "INS-01", "name": "Alexandre Martin", "max_hours_per_day": 8, "available": True},
    {"id": "INS-02", "name": "Sophie Bernard", "max_hours_per_day": 6, "available": True},
    {"id": "INS-03", "name": "Thomas Leroy", "max_hours_per_day": 8, "available": True},
    {"id": "INS-04", "name": "Julien Moreau", "max_hours_per_day": 8, "available": True},
    {"id": "INS-05", "name": "Camille Dupont", "max_hours_per_day": 5, "available": True},
    {"id": "INS-06", "name": "Marc Fontaine", "max_hours_per_day": 8, "available": False},
    {"id": "INS-07", "name": "Élise Petit", "max_hours_per_day": 8, "available": True},
]

# Liste des maintenances (exemple vide, vous pouvez en ajouter)
MAINTENANCE_SLOTS = []