# app.py (Version avec Gestion CRUD Complète)
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy.orm import joinedload
from scheduler_ortools import ATCSchedulerORTools
from export_utils import generate_excel, generate_pdf
from config_data import SIMULATORS, get_instructors, add_instructor, delete_instructor, toggle_instructor_availability
from database import SessionLocal, Promotion, Phase, TimeSlot, Instructor

st.set_page_config(page_title="ATC Planner - Gestion Complète", layout="wide")

# --- CSS ---
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- INIT ---
if 'scheduler_ortools' not in st.session_state:
    st.session_state.scheduler_ortools = ATCSchedulerORTools()
if 'current_phase_id' not in st.session_state:
    st.session_state.current_phase_id = None

# --- SIDEBAR (Historique + Gestion Instructeurs) ---
with st.sidebar:
    st.title("ATC Planner Pro")
    st.write("Moteur OR-Tools")
    
    # 1. Gestion des Instructeurs (CRUD)
    with st.expander("👨‍🏫 Gérer les instructeurs"):
        st.write("**Ajouter un instructeur :**")
        new_name = st.text_input("Nom de l'instructeur", key="new_inst_name")
        new_hours = st.number_input("Heures max / jour", min_value=1, max_value=12, value=8, key="new_inst_hours")
        if st.button("➕ Ajouter", key="btn_add_inst"):
            if new_name:
                success, msg = add_instructor(new_name, new_hours)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        st.write("---")
        st.write("**Liste des instructeurs :**")
        db = SessionLocal()
        all_instructors = db.query(Instructor).order_by(Instructor.name).all()
        for inst in all_instructors:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"{inst.name} {'(Indisponible)' if not inst.available else ''}")
            with col2:
                if st.button("🚫", key=f"del_{inst.id}", help="Supprimer cet instructeur"):
                    if delete_instructor(inst.id):
                        st.rerun()
            with col3:
                new_status = not inst.available
                if st.button("🔄", key=f"tog_{inst.id}", help="Basculer disponibilité"):
                    toggle_instructor_availability(inst.id, new_status)
                    st.rerun()
        db.close()

    # 2. Historique des Promotions
    st.subheader("Historique")
    db = SessionLocal()
    promotions = db.query(Promotion).options(joinedload(Promotion.phases)).order_by(Promotion.created_at.desc()).all()
    db.close()
    
    for promo in promotions:
        with st.expander(f"📌 {promo.name}"):
            for phase in promo.phases:
                status_emoji = "✅" if phase.status == "Terminée" else "🔄" if phase.status == "En cours" else "📅"
                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(f"{status_emoji} {phase.phase_type}", key=f"btn_{phase.id}"):
                        st.session_state.current_phase_id = phase.id
                        st.rerun()
                with col2:
                    # Bouton Supprimer la phase
                    if st.button("🗑️", key=f"del_phase_{phase.id}", help="Supprimer cette phase"):
                        db_del = SessionLocal()
                        del_phase = db_del.query(Phase).filter(Phase.id == phase.id).first()
                        if del_phase:
                            db_del.delete(del_phase)
                            db_del.commit()
                            db_del.close()
                            if st.session_state.current_phase_id == phase.id:
                                st.session_state.current_phase_id = None
                            st.rerun()

# --- PAGE PRINCIPALE ---
st.title("ATC Planner - Gestion des simulateurs")

# --- KPI ---
db = SessionLocal()
all_phases = db.query(Phase).options(joinedload(Phase.instructor_assignments)).all()
active_phases = [p for p in all_phases if p.status != "Terminée"]
all_assignments = [i for phase in all_phases for i in phase.instructor_assignments]
total_instructors_aff = len(set([i.instructor_name for i in all_assignments]))
db.close()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Promotions actives", len(active_phases), f"Total: {len(all_phases)}")
with col2:
    st.metric("Simulateurs", f"{len(SIMULATORS)} / {len(SIMULATORS)}", "Tous dispo")
with col3:
    st.metric("Instructeurs affectés", total_instructors_aff)
with col4:
    st.metric("Phases en cours", len([p for p in all_phases if p.status == 'En cours']))
st.divider()

# --- ZONE DE TRAVAIL ---
if st.session_state.current_phase_id:
    phase, slots, instructors = st.session_state.scheduler_ortools.get_phase_details(st.session_state.current_phase_id)
    if phase:
        st.subheader(f"📋 {phase.phase_type}")
        
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.metric("Date de début", phase.start_date.strftime("%d/%m/%Y"))
            st.metric("Groupes", len(set(s.group_name for s in slots)))
            
            if st.button("📊 Générer le rapport PDF"):
                pdf_buffer = generate_pdf(slots, phase.phase_type, "Promotion")
                st.download_button("Télécharger PDF", data=pdf_buffer, file_name=f"Rapport_{phase.phase_type}.pdf")
        
        with col_right:
            st.write("**Instructeurs assignés :**")
            for ins in instructors:
                st.write(f"- {ins.group_name} : {ins.instructor_name}")

        # Graphique Gantt
        if slots:
            df_plot = pd.DataFrame([{
                "group_name": s.group_name, "start": s.start_time, "end": s.end_time, 
                "simulator": s.simulator, "instructor": s.instructor_name
            } for s in slots])
            fig = px.timeline(df_plot, x_start="start", x_end="end", y="simulator", color="group_name", hover_data=["instructor"], title="Occupation des simulateurs")
            st.plotly_chart(fig, use_container_width=True)

            # --- ÉDITION AVANCÉE (Tableau modifiable) ---
            st.subheader("Modification manuelle des créneaux")
            df_edit = pd.DataFrame([{
                "ID": s.id, "Groupe": s.group_name, "Instructeur": s.instructor_name
            } for s in slots])
            
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "Instructeur": st.column_config.SelectboxColumn(
                        "Instructeur",
                        help="Changer l'instructeur pour ce créneau",
                        width="medium",
                        options=[i["name"] for i in get_instructors()]
                    )
                },
                disabled=["ID", "Groupe"],
                use_container_width=True,
                hide_index=True
            )
            
            # Détection des changements (Sauvegarde des modifications)
            changes_made = False
            for index, row in edited_df.iterrows():
                original_instructor = df_edit.iloc[index]["Instructeur"]
                new_instructor = row["Instructeur"]
                if original_instructor != new_instructor:
                    slot_id = row["ID"]
                    db_upd = SessionLocal()
                    db_upd.query(TimeSlot).filter(TimeSlot.id == slot_id).update({"instructor_name": new_instructor})
                    db_upd.commit()
                    db_upd.close()
                    changes_made = True
            
            if changes_made:
                st.success("✅ Instructeurs mis à jour avec succès !")
                st.rerun()

else:
    st.info("➕ Créez une nouvelle phase ci-dessous ou sélectionnez-en une dans l'historique.")
    with st.container(border=True):
        st.subheader("Créer une nouvelle phase (avec IA)")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            promo_name = st.text_input("Nom de la promotion", value="P2025-G")
            student_count = st.number_input("Étudiants", min_value=1, value=30)
        with col_f2:
            phase_options = ["Aérodrome", "Approche Procédures", "En-route Procédures", "Approche Radar", "En-route Radar"]
            phase_selected = st.selectbox("Phase", phase_options)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            sessions_per_student = st.number_input("Séances / étudiant", value=8)
            start_date = st.date_input("Date de début", datetime.now())
        with col_p2:
            duration_min = st.number_input("Durée (min)", value=45)
            if "Radar" in phase_selected:
                avail_pos = st.number_input("Positions RADAR", value=4)
            else:
                avail_pos = st.number_input("Positions TWR", value=4)
        
        daily_hours = st.multiselect(
            "Plages horaires", options=[8, 9, 10, 11, 13, 14, 15, 16, 17], default=[9, 10, 11, 14, 15, 16]
        )
        
        if st.button("🚀 Lancer l'optimisation OR-Tools", type="primary", use_container_width=True):
            if not daily_hours:
                st.error("Sélectionnez au moins une plage horaire.")
            else:
                with st.spinner("Le solveur planifie..."):
                    result = st.session_state.scheduler_ortools.create_phase_and_generate(
                        promo_name=promo_name,
                        student_count=student_count,
                        phase_type=phase_selected,
                        sessions_per_student=sessions_per_student,
                        duration_min=duration_min,
                        start_date=start_date,
                        available_positions=avail_pos,
                        daily_hours=sorted(daily_hours)
                    )
                    if result["status"] == "success":
                        st.success(result["message"])
                        st.session_state.current_phase_id = result["phase_id"]
                        st.rerun()
                    else:
                        st.error(result["message"])
