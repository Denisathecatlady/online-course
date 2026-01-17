from io import BytesIO
from datetime import date
import os

from django.core.files.base import ContentFile
from django.db.models import Max
from django.conf import settings

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from payments.models import Order


# ------------------------------------------------------------------
# FONTY
# ------------------------------------------------------------------

FONT_PATH = os.path.join(settings.BASE_DIR, "payments", "fonts", "DejaVuSans.ttf")

pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_PATH))


# ------------------------------------------------------------------
# ČÍSLO FAKTURY
# ------------------------------------------------------------------

def assign_invoice_number(order):
    if order.invoice_number:
        return

    last_number = (
        Order.objects
        .exclude(invoice_number__isnull=True)
        .aggregate(Max("invoice_number"))["invoice_number__max"]
    )

    order.invoice_number = (last_number or 260000) + 1
    order.save(update_fields=["invoice_number"])


# ------------------------------------------------------------------
# PDF FAKTURA
# ------------------------------------------------------------------

def generate_invoice_pdf(order):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --------------------------------------------------
    # LOGO
    # --------------------------------------------------
    logo_path = os.path.join(
        settings.BASE_DIR,
        "courses",
        "static",
        "courses",
        "logo-calmdog.png",
    )

    if os.path.exists(logo_path):
        p.drawImage(
            logo_path,
            40,
            height - 90,
            width=120,
            preserveAspectRatio=True,
            mask="auto",
        )

    # --------------------------------------------------
    # NADPIS
    # --------------------------------------------------
    p.setFont("DejaVu-Bold", 20)
    p.drawRightString(width - 40, height - 60, "FAKTURA")

    p.setFont("DejaVu", 10)
    p.drawRightString(
        width - 40,
        height - 85,
        f"Číslo faktury: {order.invoice_number}",
    )
    p.drawRightString(
        width - 40,
        height - 100,
        f"Datum vystavení: {date.today().strftime('%d.%m.%Y')}",
    )

    # --------------------------------------------------
    # DODAVATEL
    # --------------------------------------------------
    y_top = height - 150

    p.setFont("DejaVu-Bold", 11)
    p.drawString(40, y_top, "Dodavatel")

    p.setFont("DejaVu", 10)
    p.drawString(40, y_top - 18, "Ing. Andrea Zoulová")
    p.drawString(40, y_top - 33, "IČO: 19603118")
    p.drawString(40, y_top - 48, "E-mail: info@calmdog.cz")
    p.drawString(40, y_top - 63, "Nejsem plátce DPH")

    # --------------------------------------------------
    # ODBĚRATEL
    # --------------------------------------------------
    p.setFont("DejaVu-Bold", 11)
    p.drawString(300, y_top, "Odběratel")

    p.setFont("DejaVu", 10)
    p.drawString(300, y_top - 18, order.invoice_name)
    p.drawString(300, y_top - 33, order.invoice_street)
    p.drawString(
        300,
        y_top - 48,
        f"{order.invoice_zip} {order.invoice_city}",
    )

    # --------------------------------------------------
    # ČÁRA
    # --------------------------------------------------
    p.setLineWidth(0.5)
    p.line(40, y_top - 85, width - 40, y_top - 85)

    # --------------------------------------------------
    # POLOŽKY
    # --------------------------------------------------
    y = y_top - 120

    p.setFont("DejaVu-Bold", 11)
    p.drawString(40, y, "Popis")
    p.drawRightString(width - 40, y, "Cena")

    p.setFont("DejaVu", 10)
    p.drawString(
        40,
        y - 22,
        f"{order.course.title} – {order.plan.name}",
    )
    p.drawRightString(
        width - 40,
        y - 22,
        f"{order.plan.price_czk} Kč",
    )

    # --------------------------------------------------
    # CELKEM
    # --------------------------------------------------
    p.setLineWidth(0.5)
    p.line(40, y - 50, width - 40, y - 50)

    p.setFont("DejaVu-Bold", 13)
    p.drawRightString(
        width - 40,
        y - 80,
        f"Celkem k úhradě: {order.plan.price_czk} Kč",
    )

    # --------------------------------------------------
    # PATIČKA
    # --------------------------------------------------
    p.setFont("DejaVu", 9)
    p.setFillGray(0.4)
    p.drawCentredString(
        width / 2,
        40,
        "CalmDog • online kurzy o porozumění psům",
    )

    p.showPage()
    p.save()

    buffer.seek(0)

    return ContentFile(
        buffer.read(),
        name=f"faktura_{order.invoice_number}.pdf",
    )
