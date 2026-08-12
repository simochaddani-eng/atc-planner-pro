# config_data.py
from database import SessionLocal, Instructor
from sqlalchemy.exc import IntegrityError

# Configuration des simulateurs (Ressources matérielles fixes)
SIMULATORS = {
    "TWR": {"positions": 4, "type": "fixed", "mode": "Aérodrome"},
    "RADAR_1": {"positions": 4, "type": "flexible", "mode": "Approche Radar"},
    "RADAR_2": {"positions": 2, "type": "flexible", "mode": "En-route Radar"}
}

# --- GESTION DYNAMIQUE DES INSTRUCTEURS ---
def get_instructors():
    """Récupère la liste des instructeurs depuis la base de données."""
    db = SessionLocal()
    instructors = db.query(Instructor).filter(Instructor.available == True).all()
    db.close()
    # Conversion en format dictionnaire pour le reste de l'app
    return [{"id": i.id, "name": i.name, "max_hours_per_day": i.max_hours_per_day, "available": i.available} for i in instructors]

def add_instructor(name, max_hours=8):
    """Ajoute un nouvel instructeur dans la base."""
    db = SessionLocal()
    try:
        new_inst = Instructor(name=name, max_hours_per_day=max_hours, available=True)
        db.add(new_inst)
        db.commit()
        return True, f"Instructeur {name} ajouté avec succès."
    except IntegrityError:
        db.rollback()
        return False, "Un instructeur avec ce nom existe déjà."
    finally:
        db.close()

def delete_instructor(instructor_id):
    """Supprime un instructeur de la base (et le retire des plannings existants)."""
    db = SessionLocal()
    inst = db.query(Instructor).filter(Instructor.id == instructor_id).first()
    if inst:
        db.delete(inst)
        db.commit()
        db.close()
        return True
    db.close()
    return False

def toggle_instructor_availability(instructor_id, available_status):
    """Active ou désactive un instructeur."""
    db = SessionLocal()
    inst = db.query(Instructor).filter(Instructor.id == instructor_id).first()
    if inst:
        inst.available = available_status
        db.commit()
        db.close()
        return True
    db.close()
    return False

# Pour compatibilité avec l'ancien code, on expose une fonction de rafraîchissement
def refresh_instructors_list():
    return get_instructors()
