from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0011_courseaccess_expires_at"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="shipping_method",
                    field=models.CharField(blank=True, choices=[("zasilkovna", "Zásilkovna"), ("kuryr", "Kurýr")], max_length=50, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="shipping_price",
                    field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_packet_id",
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_tracking_number",
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_label_pdf",
                    field=models.FileField(blank=True, null=True, upload_to="packeta_labels/"),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_created_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_point_id",
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="packeta_point_name",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="order",
                    name="stock_reduced",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]
