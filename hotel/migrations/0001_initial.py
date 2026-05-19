from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HotelReservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_name", models.CharField(max_length=120, verbose_name="Jméno")),
                ("last_name", models.CharField(max_length=120, verbose_name="Příjmení")),
                ("email", models.EmailField(max_length=254, verbose_name="E-mail")),
                (
                    "phone",
                    models.CharField(blank=True, max_length=40, verbose_name="Telefon"),
                ),
                ("date_from", models.DateField(verbose_name="Datum příjezdu")),
                ("date_to", models.DateField(verbose_name="Datum odjezdu")),
                (
                    "pet_type",
                    models.CharField(
                        choices=[("dog", "Pes"), ("cat", "Kočka"), ("other", "Jiné")],
                        default="dog",
                        max_length=10,
                        verbose_name="Druh zvířete",
                    ),
                ),
                (
                    "pet_count",
                    models.PositiveSmallIntegerField(
                        default=1, verbose_name="Počet zvířat"
                    ),
                ),
                (
                    "pet_name",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Jméno zvířete"
                    ),
                ),
                (
                    "pet_breed",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Plemeno"
                    ),
                ),
                (
                    "is_aggressive",
                    models.BooleanField(
                        default=False, verbose_name="Projevuje agresivní chování"
                    ),
                ),
                (
                    "aggression_notes",
                    models.TextField(blank=True, verbose_name="Popis chování"),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        verbose_name="Další poznámky / speciální požadavky",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Čeká na potvrzení"),
                            ("confirmed", "Potvrzeno"),
                            ("canceled", "Zrušeno"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Stav",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
            ],
            options={
                "verbose_name": "Rezervace hotelu",
                "verbose_name_plural": "Rezervace hotelu",
                "ordering": ["-created_at"],
            },
        ),
    ]
