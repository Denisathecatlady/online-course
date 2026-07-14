from django.db import migrations


def backfill(apps, schema_editor):
    """
    Jednorázový import odběratelů ze všech dosavadních objednávek,
    kde byl souhlas s newsletterem zaškrtnut. Deduplikace přes
    lowercase e-mail – jeden člověk = jeden řádek.
    """
    Order = apps.get_model("payments", "Order")
    Subscriber = apps.get_model("payments", "NewsletterSubscriber")

    for order in Order.objects.filter(newsletter_opt_in=True).exclude(buyer_email=""):
        email = (order.buyer_email or "").strip().lower()
        if not email:
            continue
        Subscriber.objects.update_or_create(
            email=email,
            defaults={
                "first_name": (order.first_name or "").strip(),
                "last_name": (order.last_name or "").strip(),
                "is_subscribed": True,
                "source": "checkout",
            },
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0021_newslettersubscriber"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
