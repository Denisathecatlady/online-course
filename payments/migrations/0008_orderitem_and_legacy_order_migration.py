from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


def migrate_legacy_orders_to_order_items(apps, schema_editor):
    Order = apps.get_model("payments", "Order")
    OrderItem = apps.get_model("payments", "OrderItem")

    for order in Order.objects.select_related("plan").all():
        if OrderItem.objects.filter(order_id=order.id).exists():
            continue

        price = getattr(order.plan, "price_czk", None)
        if price is None:
            continue

        OrderItem.objects.create(
            order_id=order.id,
            course_plan_id=order.plan_id,
            quantity=1,
            price_at_purchase=Decimal(price),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0007_order_newsletter_opt_in"),
        ("shop", "0002_alter_productvariant_length_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="OrderItem",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("quantity", models.PositiveIntegerField(default=1)),
                        ("price_at_purchase", models.DecimalField(decimal_places=2, max_digits=10)),
                        ("course_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="payments.courseplan")),
                        ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="payments.order")),
                        ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="shop.productvariant")),
                    ],
                ),
                migrations.AlterField(
                    model_name="order",
                    name="buyer_email",
                    field=models.EmailField(blank=True, max_length=254),
                ),
                migrations.AlterField(
                    model_name="order",
                    name="first_name",
                    field=models.CharField(blank=True, max_length=120),
                ),
                migrations.AlterField(
                    model_name="order",
                    name="invoice_number",
                    field=models.PositiveIntegerField(blank=True, null=True, unique=True),
                ),
                migrations.AlterField(
                    model_name="order",
                    name="last_name",
                    field=models.CharField(blank=True, max_length=120),
                ),
                migrations.AlterField(
                    model_name="order",
                    name="newsletter_opt_in",
                    field=models.BooleanField(default=False),
                ),
                migrations.AlterField(
                    model_name="order",
                    name="status",
                    field=models.CharField(
                        choices=[
                            ("cart", "Košík"),
                            ("pending", "Čeká na platbu"),
                            ("paid", "Zaplaceno"),
                            ("failed", "Neúspěšné"),
                            ("canceled", "Zrušeno"),
                        ],
                        default="cart",
                        max_length=20,
                    ),
                ),
            ],
        ),
    ]
