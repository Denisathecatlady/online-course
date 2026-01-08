from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.core.files.base import ContentFile
from io import BytesIO
from datetime import date


def generate_invoice_pdf(order):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --------------------------------------------------
    # HLAVIČKA
    # --------------------------------------------------
    p.setFont("Helvetica-Bold", 18)
    p.drawString(40, height - 50, "Faktura")

    p.setFont("Helvetica", 10)
    p.drawString(40, height - 80, f"Číslo faktury: {order.invoice_number}")
    p.drawString(40, height - 95, f"Datum vystavení: {date.today().strftime('%d.%m.%Y')}")

    # --------------------------------------------------
    # DODAVATEL
    # --------------------------------------------------
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, height - 130, "Dodavatel:")

    p.setFont("Helvetica", 10)
    p.drawString(40, height - 145, "Ing. Andrea Zoulová")
    p.drawString(40, height - 160, "IČO: 19603118")
    p.drawString(40, height - 175, "E-mail: info@calmdog.cz")
    p.drawString(40, height - 190, "Nejsem plátce DPH")

    # --------------------------------------------------
    # ODBĚRATEL
    # --------------------------------------------------
    p.setFont("Helvetica-Bold", 10)
    p.drawString(300, height - 130, "Odběratel:")

    p.setFont("Helvetica", 10)
    p.drawString(300, height - 145, order.invoice_name)
    p.drawString(300, height - 160, order.invoice_street)
    p.drawString(300, height - 175, f"{order.invoice_zip} {order.invoice_city}")

    # --------------------------------------------------
    # POLOŽKY
    # --------------------------------------------------
    y = height - 240
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Popis")
    p.drawString(400, y, "Cena")

    p.setFont("Helvetica", 10)
    p.drawString(40, y - 20, f"{order.course.title} – {order.plan.name}")
    p.drawString(400, y - 20, f"{order.plan.price_czk} Kč")

    # --------------------------------------------------
    # CELKEM
    # --------------------------------------------------
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y - 60, f"Celkem k úhradě: {order.plan.price_czk} Kč")

    p.showPage()
    p.save()

    buffer.seek(0)
    return ContentFile(
        buffer.read(),
        name=f"faktura_{order.invoice_number}.pdf"
    )
