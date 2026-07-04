from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0019_order_paid_at_and_review_request"),
    ]

    operations = [
        migrations.CreateModel(
            name="WelcomeCouponClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, unique=True, verbose_name="E-mail")),
                (
                    "coupon",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welcome_claim",
                        to="payments.coupon",
                        verbose_name="Vytvořený kupón",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Odesláno")),
            ],
            options={
                "verbose_name": "Uvítací sleva",
                "verbose_name_plural": "Uvítací slevy",
                "ordering": ["-created_at"],
            },
        ),
    ]
