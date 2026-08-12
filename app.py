# app.py (Version FINALE avec correction de tous les DetachedInstanceError)
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy.orm import joinedload
from scheduler_ortools import ATCSchedulerORTools
from export_utils import generate_excel, generate_pdf
from config_data import INSTRUCTORS, SIMULATORS
from database import SessionLocal, Promotion, Phase, TimeSlot, InstructorAssign

st.set_page_config(page_title="ATC Planner - Dashboard", layout="wide")

# --- CHARGEMENT DU CSS ---
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- INITIALISATION DU MOTEUR ---
if 'scheduler_ortools' not in st.session_state:
    st.session_state.scheduler_ortools = ATCSchedulerORTools()
if 'current_phase_id' not in st.session_state:
    st.session_state.current_phase_id = None

# --- CHARGEMENT DES DONNÉES (EXÉCUTÉ À CHAQUE RAFRAÎCHISSEMENT) ---
db = SessionLocal()
# Requête optimisée pour la sidebar (Promotions + Phases)
promotions_sidebar = db.query(Promotion).options(
    joinedload(Promotion.phases)
).order_by(Promotion.created_at.desc()).all()
# Requête pour le Dashboard (Toutes les phases avec leurs instructeurs)
all_phases_dashboard = db.query(Phase).options(
    joinedload(Phase.instructor_assignments)
).all()
db.close()

# --- SIDEBAR ---
with st.sidebar:
    st.title("ATC Planner Pro")
    st.write("Moteur OR-Tools")
    
    st.subheader("Historique")
    for promo in promotions_sidebar:
        with st.expander(f"📌 {promo.name}"):
            for phase in promo.phases:
                status_emoji = "✅" if phase.status == "Terminée" else "🔄" if phase.status == "En cours" else "📅"
                if st.button(f"{status_emoji} {phase.phase_type}", key=f"btn_{phase.id}"):
                    st.session_state.current_phase_id = phase.id
                    st.rerun()

# --- PAGE PRINCIPALE DASHBOARD ---
st.title("ATC Planner - Gestion des simulateurs")

# --- PARTIE 1 : LES 4 ENCARTS KPI ---
# Calcul des stats basé sur les listes déjà chargées en mémoire
active_phases = [p for p in all_phases_dashboard if p.status != "Terminée"]
all_assignments = [i for phase in all_phases_dashboard for i in phase.instructor_assignments]
total_instructors_aff = len(set([i.instructor_name for i in all_assignments]))

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Promotions actives</div>
        <div class="kpi-value">{len(active_phases)}</div>
        <div class="kpi-delta">📚 Total : {len(all_phases_dashboard)} phases</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Simulateurs disponibles</div>
        <div class="kpi-value">{len(SIMULATORS)} / {len(SIMULATORS)}</div>
        <div class="kpi-delta">🖥️ Toutes positions OK</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Instructeurs affectés</div>
        <div class="kpi-value">{total_instructors_aff}</div>
        <div class="kpi-delta">👨‍🏫 Sur les phases actives</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Phases en cours</div>
        <div class="kpi-value">{len([p for p in all_phases_dashboard if p.status == 'En cours'])}</div>
        <div class="kpi-delta">🔄 {len([p for p in all_phases_dashboard if p.status == 'Planifiée'])} planifiées</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- PARTIE 2 : ZONE DE CRÉATION OU VISUALISATION ---
if st.session_state.current_phase_id:
    phase, slots, instructors = st.session_state.scheduler_ortools.get_phase_details(st.session_state.current_phase_id)
    
    if phase:
        # CORRECTION ICI : On récupère le nom de la promotion via une nouvelle requête pour éviter l'erreur
        db = SessionLocal()
        promo_name = db.query(Promotion.name).filter(Promotion.id == phase.promotion_id).scalar()
        db.close()
        
        st.subheader(f"📋 {phase.phase_type} - {promo_name}")
        
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.metric("Date de début", phase.start_date.strftime("%d/%m/%Y"))
            st.metric("Date de fin estimée", phase.end_date_estimated.strftime("%d/%m/%Y") if phase.end_date_estimated else "Non définie")
            st.metric("Groupes", len(set(s.group_name for s in slots)))
            
            if st.button("📊 Générer le rapport PDF", key="btn_pdf"):
                pdf_buffer = generate_pdf(slots, phase.phase_type, promo_name)
                st.download_button("Télécharger PDF", data=pdf_buffer, file_name=f"Rapport_{phase.phase_type}.pdf")
            if st.button("📊 Générer le rapport Excel", key="btn_xlsx"):
                excel_buffer = generate_excel(slots, phase.phase_type)
                st.download_button("Télécharger Excel", data=excel_buffer, file_name=f"Rapport_{phase.phase_type}.xlsx")

        with col_right:
            st.write("**Instructeurs :**")
            for ins in instructors:
                st.write(f"- {ins.group_name} : {ins.instructor_name}")

        # Graphique Gantt
        if slots:
            df_plot = pd.DataFrame([{
                "group_name": s.group_name,
                "start": s.start_time,
                "end": s.end_time,
                "simulator": s.simulator,
                "instructor": s.instructor_name
            } for s in slots])
            fig = px.timeline(df_plot, x_start="start", x_end="end", y="simulator", color="group_name", 
                              hover_data=["instructor"], title="Occupation des simulateurs")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("➕ Créez une nouvelle phase de simulation ci-dessous.")
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
                with st.spinner("Le solveur d'optimisation planifie les séances..."):
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
