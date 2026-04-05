from django.db import migrations


def add_expires_at_column_if_missing(apps, schema_editor):
    table_name = "payments_courseaccess"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

        if "expires_at" not in existing_columns:
            cursor.execute(
                f'ALTER TABLE "{table_name}" ADD COLUMN "expires_at" datetime NULL'
            )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_order_shipping_and_packeta_fields"),
    ]

    operations = [
        migrations.RunPython(add_expires_at_column_if_missing, migrations.RunPython.noop),
    ]
