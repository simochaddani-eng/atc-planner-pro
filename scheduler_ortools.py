# scheduler_ortools.py
import datetime
from ortools.sat.python import cp_model
from database import SessionLocal, Promotion, Phase, TimeSlot, InstructorAssign
from config_data import get_instructors

class ATCSchedulerORTools:
    
    def calculate_metrics(self, student_count, sessions_per_student, duration_min, available_positions):
        groups = (student_count + available_positions - 1) // available_positions
        total_sessions = student_count * sessions_per_student
        total_hours = (total_sessions * duration_min) / 60
        return groups, total_sessions, total_hours

    def create_phase_and_generate(self, promo_name, student_count, phase_type, sessions_per_student, 
                                  duration_min, start_date, available_positions, daily_hours, maintenance_slots=None):
        
        db = SessionLocal()
        
        # 1. Création de la Promotion / Phase en base
        promo = db.query(Promotion).filter(Promotion.name == promo_name).first()
        if not promo:
            promo = Promotion(name=promo_name, student_count=student_count)
            db.add(promo)
            db.commit()
            db.refresh(promo)

        groups_count, _, _ = self.calculate_metrics(
            student_count, sessions_per_student, duration_min, available_positions
        )
        
        slots_per_day = len(daily_hours) if len(daily_hours) > 0 else 1
        days_needed = (groups_count * sessions_per_student) / (available_positions * slots_per_day)
        end_date = start_date + datetime.timedelta(days=int(days_needed) + 1)

        new_phase = Phase(
            promotion_id=promo.id,
            phase_type=phase_type,
            sessions_per_student=sessions_per_student,
            duration_min=duration_min,
            available_positions=available_positions,
            start_date=start_date,
            end_date_estimated=end_date,
            status="Planifiée"
        )
        db.add(new_phase)
        db.commit()
        db.refresh(new_phase)

        # 2. CONFIGURATION DU MODÈLE OR-TOOLS
        model = cp_model.CpModel()
        
        candidate_starts = []
        current_day = start_date
        for day in range(30): 
            for hour in daily_hours:
                start_dt = datetime.datetime.combine(current_day, datetime.time(hour, 0))
                is_maint = False
                if maintenance_slots:
                    for maint in maintenance_slots:
                        if start_dt.date() == datetime.datetime.strptime(maint['date'], "%Y-%m-%d").date():
                            is_maint = True
                            break
                if not is_maint:
                    candidate_starts.append(start_dt)
            current_day += datetime.timedelta(days=1)

        num_slots = len(candidate_starts)
        if num_slots == 0:
            db.close()
            return {"status": "failure", "message": "Aucun créneau horaire disponible avec les contraintes actuelles."}

        session_vars = {}
        for g in range(1, groups_count + 1):
            for s in range(1, sessions_per_student + 1):
                key = f"G{g}_S{s}"
                session_vars[key] = model.NewIntVar(0, num_slots - 1, key)
        
        model.AddAllDifferent(session_vars.values())

        # 3. Résolution
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            # --- CORRECTION ICI : On utilise la base de données dynamique ---
            available_instructors = get_instructors()
            # --------------------------------------------------------------
            
            plan_slots = []
            for g in range(1, groups_count + 1):
                instructor = available_instructors[(g - 1) % len(available_instructors)]
                
                assign = InstructorAssign(
                    phase_id=new_phase.id,
                    group_name=f"Groupe {g}",
                    instructor_id=instructor["id"],
                    instructor_name=instructor["name"]
                )
                db.add(assign)
                
                for s in range(1, sessions_per_student + 1):
                    key = f"G{g}_S{s}"
                    slot_index = solver.Value(session_vars[key])
                    start_time = candidate_starts[slot_index]
                    end_time = start_time + datetime.timedelta(minutes=duration_min)
                    
                    slot = TimeSlot(
                        phase_id=new_phase.id,
                        group_name=f"Groupe {g}",
                        session_number=s,
                        start_time=start_time,
                        end_time=end_time,
                        simulator="TWR" if "Aérodrome" in phase_type else "RADAR",
                        instructor_name=instructor["name"]
                    )
                    db.add(slot)
                    plan_slots.append(slot)
            
            db.commit()
            
            # Lecture des données avant fermeture
            phase_id_final = new_phase.id
            groups_count_final = groups_count
            total_hours_final = round((groups_count * sessions_per_student * duration_min) / 60, 1)
            end_date_final = end_date.strftime("%d/%m/%Y")
            message_final = f"Planning optimal généré par OR-Tools pour {promo_name}."
            
            db.close()
            
            return {
                "status": "success",
                "phase_id": phase_id_final,
                "groups_count": groups_count_final,
                "total_hours": total_hours_final,
                "end_date": end_date_final,
                "message": message_final
            }
        else:
            db.delete(new_phase)
            db.commit()
            db.close()
            return {"status": "failure", "message": "Impossible de trouver un planning valide. Veuillez augmenter les plages horaires ou réduire le nombre de groupes."}

    def recalculate_phase_ortools(self, phase_id, daily_hours):
        db = SessionLocal()
        phase = db.query(Phase).filter(Phase.id == phase_id).first()
        if not phase:
            db.close()
            return {"status": "failure", "message": "Phase introuvable."}
        
        db.query(TimeSlot).filter(TimeSlot.phase_id == phase_id).delete()
        db.query(InstructorAssign).filter(InstructorAssign.phase_id == phase_id).delete()
        db.commit()
        
        promo = phase.promotion
        result = self.create_phase_and_generate(
            promo_name=promo.name,
            student_count=promo.student_count,
            phase_type=phase.phase_type,
            sessions_per_student=phase.sessions_per_student,
            duration_min=phase.duration_min,
            start_date=phase.start_date,
            available_positions=phase.available_positions,
            daily_hours=daily_hours
        )
        db.close()
        return result

    def get_phase_details(self, phase_id):
        db = SessionLocal()
        phase = db.query(Phase).filter(Phase.id == phase_id).first()
        slots = db.query(TimeSlot).filter(TimeSlot.phase_id == phase_id).order_by(TimeSlot.start_time).all()
        instructors = db.query(InstructorAssign).filter(InstructorAssign.phase_id == phase_id).all()
        db.close()
        return phase, slots, instructors

    def update_phase_status(self, phase_id, new_status):
        db = SessionLocal()
        phase = db.query(Phase).filter(Phase.id == phase_id).first()
        if phase:
            phase.status = new_status
            db.commit()
        db.close()
