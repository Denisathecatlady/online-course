from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0010_switch_course_plan_relations_to_courses_app"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="courseaccess",
                    name="expires_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
