# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from scheduler_ortools import ATCSchedulerORTools
from export_utils import generate_excel, generate_pdf
from config_data import INSTRUCTORS
from database import SessionLocal, Promotion

st.set_page_config(page_title="ATC Planner - OR-Tools", layout="wide")

if 'scheduler_ortools' not in st.session_state:
    st.session_state.scheduler_ortools = ATCSchedulerORTools()
if 'current_phase_id' not in st.session_state:
    st.session_state.current_phase_id = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("ATC Planner Pro")
    st.write("Moteur OR-Tools")
    
    db = SessionLocal()
    promotions = db.query(Promotion).order_by(Promotion.created_at.desc()).all()
    db.close()
    
    st.subheader("Historique")
    for promo in promotions:
        with st.expander(f"📌 {promo.name}"):
            for phase in promo.phases:
                status_emoji = "✅" if phase.status == "Terminée" else "🔄" if phase.status == "En cours" else "📅"
                if st.button(f"{status_emoji} {phase.phase_type}", key=f"btn_{phase.id}"):
                    st.session_state.current_phase_id = phase.id
                    st.rerun()
    
    st.divider()
    st.caption(f"Instructeurs dispo : {sum(1 for i in INSTRUCTORS if i['available'])}/{len(INSTRUCTORS)}")

# --- PAGE PRINCIPALE ---
st.title("Planification Optimisée (IA)")

if st.session_state.current_phase_id:
    phase, slots, instructors = st.session_state.scheduler_ortools.get_phase_details(st.session_state.current_phase_id)
    
    if phase:
        col_t1, col_t2, col_t3 = st.columns([3, 1, 1])
        with col_t1:
            st.subheader(f"{phase.phase_type} - {phase.promotion.name}")
        with col_t2:
            current_status = st.selectbox(
                "Statut", 
                ["Planifiée", "En cours", "Terminée"],
                index=["Planifiée", "En cours", "Terminée"].index(phase.status)
            )
            if current_status != phase.status:
                st.session_state.scheduler_ortools.update_phase_status(phase.id, current_status)
                st.rerun()
        with col_t3:
            st.write(f"Date fin : **{phase.end_date_estimated.strftime('%d/%m/%Y')}**")
            st.write(f"Positions : **{phase.available_positions}**")
            st.write(f"Groupes : **{len(set(s.group_name for s in slots))}**")

        col_actions, col_recalc = st.columns([2, 2])
        with col_actions:
            st.write("📥 Exports :")
            if st.button("📄 PDF", key="export_pdf"):
                pdf_buffer = generate_pdf(slots, phase.phase_type, phase.promotion.name)
                st.download_button("Télécharger le PDF", data=pdf_buffer, file_name=f"Planning_{phase.phase_type}.pdf", mime="application/pdf")
            if st.button("📊 Excel", key="export_xlsx"):
                excel_buffer = generate_excel(slots, phase.phase_type)
                st.download_button("Télécharger Excel", data=excel_buffer, file_name=f"Planning_{phase.phase_type}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        with col_recalc:
            st.write("⚙️ Recalcul (Optimisation) :")
            recalc_hours = st.multiselect(
                "Nouvelles plages horaires",
                options=[8,9,10,11,13,14,15,16,17],
                default=[9,10,11,14,15,16]
            )
            if st.button("🔁 Recalculer avec OR-Tools", type="secondary"):
                if not recalc_hours:
                    st.error("Sélectionnez au moins une plage horaire.")
                else:
                    with st.spinner("Le solveur OR-Tools recalcule le planning..."):
                        result = st.session_state.scheduler_ortools.recalculate_phase_ortools(phase.id, sorted(recalc_hours))
                        if result["status"] == "success":
                            st.success("Planning optimal régénéré !")
                            st.rerun()
                        else:
                            st.error(result["message"])

        st.divider()
        
        # Affichage Instructeurs
        st.subheader("👨‍🏫 Instructeurs assignés")
        for ins in instructors:
            st.write(f"- **{ins.group_name}** : {ins.instructor_name}")
        
        # Affichage Planning
        st.subheader("📅 Planning généré par l'IA")
        if slots:
            df_plot = pd.DataFrame([{
                "group_name": s.group_name,
                "start": s.start_time,
                "end": s.end_time,
                "simulator": s.simulator,
                "instructor": s.instructor_name
            } for s in slots])
            
            fig = px.timeline(
                df_plot, 
                x_start="start", 
                x_end="end", 
                y="simulator", 
                color="group_name",
                hover_data=["instructor"],
                title="Occupation des simulateurs (Optimal)"
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Sélectionnez une phase existante ou créez-en une nouvelle.")
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
            "Plages horaires",
            options=[8, 9, 10, 11, 13, 14, 15, 16, 17],
            default=[9, 10, 11, 14, 15, 16]
        )
        
        if st.button("🚀 Lancer l'optimisation OR-Tools", type="primary", use_container_width=True):
            if not daily_hours:
                st.error("Sélectionnez au moins une plage horaire.")
            else:
                with st.spinner("Le solveur d'optimisation cherche la meilleure solution..."):
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