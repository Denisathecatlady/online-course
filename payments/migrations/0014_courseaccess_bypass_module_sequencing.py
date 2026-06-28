from django.db import migrations, models


def add_bypass_column_if_missing(apps, schema_editor):
    table_name = "payments_courseaccess"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

        if "bypass_module_sequencing" not in existing_columns:
            cursor.execute(
                f'ALTER TABLE "{table_name}" ADD COLUMN "bypass_module_sequencing" boolean NOT NULL DEFAULT FALSE'
            )


def grandfather_existing_accesses(apps, schema_editor):
    CourseAccess = apps.get_model("payments", "CourseAccess")
    CourseAccess.objects.update(bypass_module_sequencing=True)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0013_courseaccess_expires_at_db_fix"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_bypass_column_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="courseaccess",
                    name="bypass_module_sequencing",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
        migrations.RunPython(grandfather_existing_accesses, migrations.RunPython.noop),
    ]
