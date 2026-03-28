from collections import Counter, defaultdict

from django.core.management.color import no_style
from django.db import migrations


def copy_legacy_course_plans(apps, schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())
    if "payments_courseplan" not in tables:
        return

    Course = apps.get_model("courses", "Course")
    NewCoursePlan = apps.get_model("courses", "CoursePlan")
    LegacyCoursePlan = apps.get_model("payments", "CoursePlan")
    Order = apps.get_model("payments", "Order")
    CourseAccess = apps.get_model("payments", "CourseAccess")

    if not Course.objects.exists() or not LegacyCoursePlan.objects.exists():
        return

    fallback_course = Course.objects.order_by("id").first()
    plan_course_counts = defaultdict(Counter)

    for order in Order.objects.exclude(plan_id__isnull=True).exclude(course_id__isnull=True).values_list("plan_id", "course_id"):
        plan_course_counts[order[0]][order[1]] += 1

    for access in CourseAccess.objects.exclude(plan_id__isnull=True).exclude(course_id__isnull=True).values_list("plan_id", "course_id"):
        plan_course_counts[access[0]][access[1]] += 1

    for legacy_plan in LegacyCoursePlan.objects.order_by("id"):
        if NewCoursePlan.objects.filter(id=legacy_plan.id).exists():
            continue

        course_id = None
        if legacy_plan.id in plan_course_counts:
            course_id = plan_course_counts[legacy_plan.id].most_common(1)[0][0]
        elif fallback_course:
            course_id = fallback_course.id

        if course_id is None:
            continue

        NewCoursePlan.objects.create(
            id=legacy_plan.id,
            course_id=course_id,
            name=legacy_plan.name,
            code=legacy_plan.code,
            price=legacy_plan.price_czk,
            includes_certificate=legacy_plan.includes_certificate,
            includes_consultation=legacy_plan.includes_consultation,
            access_duration_days=180,
            is_active=legacy_plan.is_active,
        )

    sequence_sql = schema_editor.connection.ops.sequence_reset_sql(
        no_style(),
        [NewCoursePlan],
    )
    for sql in sequence_sql:
        schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0006_courseplan_access_duration_days_alter_module_slug_and_more"),
        ("payments", "0008_orderitem_and_legacy_order_migration"),
    ]

    operations = [
        migrations.RunPython(copy_legacy_course_plans, migrations.RunPython.noop),
    ]
