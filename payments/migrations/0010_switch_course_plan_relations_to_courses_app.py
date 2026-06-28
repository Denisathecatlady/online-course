import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0009_copy_legacy_course_plans_to_courses"),
        ("shop", "0004_alter_cartitem_options_alter_cartitem_course_plan"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Přepojí FK z payments.courseplan → courses.courseplan
                # a odstraní staré sloupce z payments_order.
                # Na existující DB (produkce) tato migrace již byla aplikována.
                migrations.AlterField(
                    model_name="orderitem",
                    name="course_plan",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="courses.courseplan"),
                ),
                migrations.AlterField(
                    model_name="courseaccess",
                    name="plan",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accesses", to="courses.courseplan"),
                ),
                migrations.RemoveField(
                    model_name="order",
                    name="course",
                ),
                migrations.RemoveField(
                    model_name="order",
                    name="plan",
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="courseaccess",
                    name="plan",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accesses", to="courses.courseplan"),
                ),
                migrations.AlterField(
                    model_name="orderitem",
                    name="course_plan",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="courses.courseplan"),
                ),
                migrations.RemoveField(
                    model_name="order",
                    name="course",
                ),
                migrations.RemoveField(
                    model_name="order",
                    name="plan",
                ),
                migrations.DeleteModel(
                    name="CoursePlan",
                ),
            ],
        ),
    ]
