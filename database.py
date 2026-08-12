# database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "atc_planner.db")

engine = create_engine(f'sqlite:///{DB_NAME}', echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- MODÈLES ---
class Promotion(Base):
    __tablename__ = 'promotions'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    student_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    phases = relationship("Phase", back_populates="promotion", cascade="all, delete-orphan")

class Phase(Base):
    __tablename__ = 'phases'
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey('promotions.id'))
    phase_type = Column(String, nullable=False)
    sessions_per_student = Column(Integer, nullable=False)
    duration_min = Column(Integer, nullable=False)
    available_positions = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date_estimated = Column(Date)
    status = Column(String, default="Planifiée")
    
    promotion = relationship("Promotion", back_populates="phases")
    slots = relationship("TimeSlot", back_populates="phase", cascade="all, delete-orphan")
    instructor_assignments = relationship("InstructorAssign", back_populates="phase", cascade="all, delete-orphan")

class TimeSlot(Base):
    __tablename__ = 'timeslots'
    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey('phases.id'))
    group_name = Column(String, nullable=False)
    session_number = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    simulator = Column(String, nullable=False)
    instructor_name = Column(String)
    
    phase = relationship("Phase", back_populates="slots")

class InstructorAssign(Base):
    __tablename__ = 'instructor_assigns'
    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey('phases.id'))
    group_name = Column(String)
    instructor_id = Column(String)
    instructor_name = Column(String)
    
    phase = relationship("Phase", back_populates="instructor_assignments")

Base.metadata.create_all(bind=engine)