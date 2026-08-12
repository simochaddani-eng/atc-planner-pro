# export_utils.py
import io
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

def generate_excel(slots_data, phase_name):
    if not slots_data:
        return None
    
    df = pd.DataFrame([{
        "Groupe": s.group_name,
        "Session": s.session_number,
        "Simulateur": s.simulator,
        "Instructeur": s.instructor_name,
        "Début": s.start_time.strftime("%d/%m/%Y %H:%M"),
        "Fin": s.end_time.strftime("%d/%m/%Y %H:%M"),
        "Durée (min)": int((s.end_time - s.start_time).total_seconds() / 60)
    } for s in slots_data])
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=f"Planning {phase_name}", index=False)
        worksheet = writer.sheets[f"Planning {phase_name}"]
        for i, col in enumerate(df.columns):
            worksheet.set_column(i, i, 20)
    buffer.seek(0)
    return buffer

def generate_pdf(slots_data, phase_name, promo_name):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    title_style.alignment = 1
    
    elements.append(Paragraph(f"Planning : {phase_name} - {promo_name}", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    data = [["Groupe", "Sess.", "Simulateur", "Instructeur", "Début", "Fin", "Durée"]]
    for s in slots_data:
        data.append([
            s.group_name,
            str(s.session_number),
            s.simulator,
            s.instructor_name,
            s.start_time.strftime("%d/%m %H:%M"),
            s.end_time.strftime("%d/%m %H:%M"),
            str(int((s.end_time - s.start_time).total_seconds() / 60)) + "min"
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer