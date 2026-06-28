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

    # 👉 ADRESA DODAVATELE – NOVĚ
    p.drawString(40, y_top - 48, "Dobrošovská 770")
    p.drawString(40, y_top - 63, "547 01 Náchod")

    p.drawString(40, y_top - 78, "E-mail: info@calmdog.cz")
    p.drawString(40, y_top - 93, "Nejsem plátce DPH")

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
    p.line(40, y_top - 115, width - 40, y_top - 115)

    # --------------------------------------------------
    # POLOŽKY
    # --------------------------------------------------
    y = y_top - 150

    p.setFont("DejaVu-Bold", 11)
    p.drawString(40, y, "Popis")
    p.drawRightString(width - 40, y, "Cena")

    p.setFont("DejaVu", 10)

    line_y = y - 22
    total_amount = 0

    for item in order.items.select_related("course_plan__course", "product_variant__product").all():
        if item.course_plan:
            description = f"Online kurz {item.course_plan.course.title}, varianta {item.course_plan.name}"
        elif item.product_variant:
            description = item.product_variant.product.name
        else:
            description = f"Polozka #{item.id}"

        p.drawString(40, line_y, description[:75])
        p.drawRightString(width - 40, line_y, f"{item.subtotal:.2f} Kč")
        total_amount += item.subtotal
        line_y -= 18

    if order.shipping_price:
        p.drawString(40, line_y, f"Doprava - {order.get_shipping_method_display() or 'bez specifikace'}")
        p.drawRightString(width - 40, line_y, f"{order.shipping_price:.2f} Kč")
        total_amount += order.shipping_price
        line_y -= 18

    if order.discount_amount and order.discount_amount > 0:
        coupon_code = order.coupon.code if order.coupon else "sleva"
        p.drawString(40, line_y, f"Sleva ({coupon_code})")
        p.drawRightString(width - 40, line_y, f"-{order.discount_amount:.2f} Kč")
        total_amount -= order.discount_amount
        line_y -= 18

    # --------------------------------------------------
    # CELKEM
    # --------------------------------------------------
    p.setLineWidth(0.5)
    p.line(40, line_y - 10, width - 40, line_y - 10)

    p.setFont("DejaVu-Bold", 13)
    p.drawRightString(
        width - 40,
        line_y - 40,
        f"Celkem k úhradě: {total_amount:.2f} Kč",
    )

    # --------------------------------------------------
    # PATIČKA
    # --------------------------------------------------
    p.setFont("DejaVu", 9)
    p.setFillGray(0.4)
    p.drawCentredString(
        width / 2,
        40,
        "CalmDog • Online kurzy",
    )

    p.showPage()
    p.save()

    buffer.seek(0)

    return ContentFile(
        buffer.read(),
        name=f"faktura_{order.invoice_number}.pdf",
    )
