# Data-migrace: stávající uživatelé (založení před allauth) nemají záznam
# EmailAddress, takže by se nemohli přihlásit e-mailem. Založíme jim ověřenou
# primární adresu z User.email.

from django.db import migrations


def backfill_email_addresses(apps, schema_editor):
    User = apps.get_model("auth", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")

    for user in User.objects.exclude(email="").iterator():
        email = (user.email or "").strip()
        if not email:
            continue
        # Uživatel už nějaký záznam má – neřešíme.
        if EmailAddress.objects.filter(user_id=user.pk).exists():
            continue
        # Stejný e-mail už patří jinému uživateli – bezpečně přeskočíme.
        if EmailAddress.objects.filter(email__iexact=email).exists():
            continue
        EmailAddress.objects.create(
            user_id=user.pk,
            email=email,
            verified=True,
            primary=True,
        )


def noop_reverse(apps, schema_editor):
    # Zpětně nic nemažeme.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_dog"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        migrations.RunPython(backfill_email_addresses, noop_reverse),
    ]
