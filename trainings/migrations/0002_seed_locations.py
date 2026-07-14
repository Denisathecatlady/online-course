"""
Datová migrace: založí výchozí lokality (Žatec, Náchod) a výchozího trenéra.

Trenérův e-mail i Google kalendář se doladí v administraci. Řešení je
rozšiřitelné – další lokality/trenéry lze kdykoli přidat v adminu.
"""

from django.db import migrations


def seed(apps, schema_editor):
    Location = apps.get_model("trainings", "Location")
    Trainer = apps.get_model("trainings", "Trainer")

    zatec, _ = Location.objects.get_or_create(
        slug="zatec", defaults={"name": "Žatec", "order": 0}
    )
    nachod, _ = Location.objects.get_or_create(
        slug="nachod", defaults={"name": "Náchod", "order": 1}
    )

    trainer, _ = Trainer.objects.get_or_create(
        email="info@calmdog.cz",
        defaults={"name": "CalmDog trenér"},
    )
    trainer.locations.add(zatec, nachod)


def unseed(apps, schema_editor):
    Location = apps.get_model("trainings", "Location")
    Trainer = apps.get_model("trainings", "Trainer")
    Trainer.objects.filter(email="info@calmdog.cz").delete()
    Location.objects.filter(slug__in=["zatec", "nachod"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("trainings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
