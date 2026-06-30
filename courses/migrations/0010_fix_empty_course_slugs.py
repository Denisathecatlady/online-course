from django.db import migrations
from django.utils.text import slugify


def fix_empty_slugs(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    for course in Course.objects.filter(slug=""):
        base = slugify(course.title) or "kurz"
        slug = base
        i = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        course.slug = slug
        course.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0009_alter_course_options_alter_courseplan_options_and_more"),
    ]

    operations = [
        migrations.RunPython(fix_empty_slugs, migrations.RunPython.noop),
    ]
