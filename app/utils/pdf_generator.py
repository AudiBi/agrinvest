from flask import render_template
from xhtml2pdf import pisa
from datetime import datetime

def generate_contract_pdf(app, investor_name, farmer_name, project_title, amount, output_path):
    with app.app_context():
        html = render_template("contract_template.html",
                               investor_name=investor_name,
                               farmer_name=farmer_name,
                               project_title=project_title,
                               amount=amount,
                               date=datetime.utcnow().strftime("%d/%m/%Y"))
        with open(output_path, "wb") as f:
            pisa_status = pisa.CreatePDF(html, dest=f)
    return pisa_status.err == 0
