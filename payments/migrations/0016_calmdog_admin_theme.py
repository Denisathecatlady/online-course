from django.db import migrations


# Historicky tato migrace vytvářela motiv administrace přes balík
# django-admin-interface (v šalvějově zelené). Ten byl nahrazen vlastním
# verzovaným design-systémem CalmDog (templates/admin/ +
# courses/static/admin/css/calmdog_admin.css), proto je migrace nyní prázdná.
#
# Ponecháváme ji (stejný název uzlu) kvůli návaznosti – 0017 na ni závisí –
# a kvůli konzistenci historie migrací na již nasazených prostředích.
# Případný starý řádek v tabulce admin_interface_theme je neškodný: balík už
# není v INSTALLED_APPS, takže se ignoruje.


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0015_alter_courseaccess_options_alter_order_options_and_more"),
    ]

    operations = []
