from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0016_calmdog_admin_theme"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "shop_locked",
                    models.BooleanField(
                        default=False,
                        help_text="Zaskrtnutim uzamknete kosik a tlacitka Pridat do kosiku. Stranky zustaji dostupne, existujici pristupy ke kurzum fungují.",
                        verbose_name="Prodej uzamčen",
                    ),
                ),
            ],
            options={
                "verbose_name": "Nastavení obchodu",
                "verbose_name_plural": "Nastavení obchodu",
            },
        ),
    ]
