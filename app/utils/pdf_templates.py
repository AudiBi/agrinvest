# app/utils/pdf_templates.py
"""
Génération de templates PDF pour AgriInvest Haïti
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from datetime import datetime


def render_contract_pdf_template(contribution):
    """
    Génère le PDF du contrat d'investissement
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2E7D32'),
        alignment=1,
        spaceAfter=30
    )
    
    normal_style = styles['Normal']
    
    story = []
    
    # Titre
    story.append(Paragraph("Contrat d'investissement agricole", title_style))
    story.append(Spacer(1, 20))
    
    # Date
    story.append(Paragraph(f"Fait le {datetime.now().strftime('%d/%m/%Y')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Parties
    story.append(Paragraph("<b>Entre les soussignés :</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"- {contribution.investor.name}, ci-après dénommé 'l'Investisseur'", normal_style))
    story.append(Paragraph(f"- {contribution.project.farmer.name}, ci-après dénommé 'l'Agriculteur'", normal_style))
    story.append(Spacer(1, 20))
    
    # Article 1
    story.append(Paragraph("<b>Article 1 - Objet du contrat</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Le présent contrat a pour objet de formaliser l'investissement de "
        f"{contribution.amount_htg:,.0f} HTG dans le projet '{contribution.project.title}'.",
        normal_style
    ))
    story.append(Spacer(1, 20))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def render_report_pdf_template(project, contributions):
    """
    Génère le PDF du rapport de projet
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"Rapport du projet : {project.title}", styles['Heading1']))
    story.append(Spacer(1, 20))
    
    total = sum(c.amount_htg for c in contributions)
    story.append(Paragraph(f"Total collecté : {total:,.0f} HTG", styles['Normal']))
    story.append(Paragraph(f"Nombre d'investisseurs : {len(contributions)}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer