"""
Opravná migrace pro čerstvé databáze (staging, nová produkce).

Migrace 0004, 0005, 0006, 0007, 0012 používaly SeparateDatabaseAndState
s database_operations=[] a spoléhaly na to, že stávající produkční DB
sloupce již obsahuje. Na čerstvé PostgreSQL DB tyto sloupce chybí.

Tato migrace přidá všechny chybějící sloupce. Na PostgreSQL (produkce,
staging) beze změny používá stejné no-op-safe IF NOT EXISTS SQL jako dřív.
Na SQLite (lokální `manage.py test`) přidá stejné sloupce portable cestou
přes Python introspekci, protože Postgres syntaxe (DO $$, information_schema,
ADD COLUMN IF NOT EXISTS, ALTER COLUMN ... DROP NOT NULL) na SQLite neexistuje.
"""

import copy

from django.db import migrations

FIX_SQL = """
-- ── 1. Přejmenovat starý sloupec s překlepem (0004) ───────────────────────
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'payments_order'
      AND column_name = 'stripe_payment_intend_id'
  ) THEN
    ALTER TABLE payments_order
      RENAME COLUMN stripe_payment_intend_id TO stripe_payment_intent_id;
  END IF;
END $$;

-- ── 2. Přidat chybějící sloupce payments_order ────────────────────────────

-- z migrace 0004
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS stripe_payment_intent_id varchar(255) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS buyer_email varchar(254) NOT NULL DEFAULT '';

-- z migrace 0005
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS first_name varchar(120) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS last_name varchar(120) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS phone varchar(40) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS street varchar(255) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS city varchar(120) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS zip_code varchar(20) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS country varchar(2) NOT NULL DEFAULT 'CZ';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_name varchar(255) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_street varchar(255) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_city varchar(120) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_zip varchar(20) NOT NULL DEFAULT '';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_country varchar(2) NOT NULL DEFAULT 'CZ';
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_pdf varchar(100);

-- z migrace 0006
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS invoice_number integer;

-- z migrace 0007
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS newsletter_opt_in boolean NOT NULL DEFAULT false;

-- z migrace 0012
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS shipping_method varchar(50);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS shipping_price decimal(10,2) NOT NULL DEFAULT 0;
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_packet_id varchar(100);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_tracking_number varchar(100);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_label_pdf varchar(100);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_created_at timestamp with time zone;
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_point_id varchar(100);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS packeta_point_name varchar(255);
ALTER TABLE payments_order
  ADD COLUMN IF NOT EXISTS stock_reduced boolean NOT NULL DEFAULT false;

-- ── 3. Nullability user_id (z migrace 0004 / 0015) ───────────────────────
ALTER TABLE payments_order ALTER COLUMN user_id DROP NOT NULL;
"""

# Same 26 columns as FIX_SQL's ADD COLUMN list, same types/defaults, minus
# "IF NOT EXISTS" (SQLite's ADD COLUMN doesn't support that clause at all —
# existence is checked in Python instead, below).
SQLITE_MISSING_COLUMNS = [
    ("stripe_payment_intent_id", "varchar(255) NOT NULL DEFAULT ''"),
    ("buyer_email", "varchar(254) NOT NULL DEFAULT ''"),
    ("first_name", "varchar(120) NOT NULL DEFAULT ''"),
    ("last_name", "varchar(120) NOT NULL DEFAULT ''"),
    ("phone", "varchar(40) NOT NULL DEFAULT ''"),
    ("street", "varchar(255) NOT NULL DEFAULT ''"),
    ("city", "varchar(120) NOT NULL DEFAULT ''"),
    ("zip_code", "varchar(20) NOT NULL DEFAULT ''"),
    ("country", "varchar(2) NOT NULL DEFAULT 'CZ'"),
    ("invoice_name", "varchar(255) NOT NULL DEFAULT ''"),
    ("invoice_street", "varchar(255) NOT NULL DEFAULT ''"),
    ("invoice_city", "varchar(120) NOT NULL DEFAULT ''"),
    ("invoice_zip", "varchar(20) NOT NULL DEFAULT ''"),
    ("invoice_country", "varchar(2) NOT NULL DEFAULT 'CZ'"),
    ("invoice_pdf", "varchar(100)"),
    ("invoice_number", "integer"),
    ("newsletter_opt_in", "boolean NOT NULL DEFAULT false"),
    ("shipping_method", "varchar(50)"),
    ("shipping_price", "decimal(10,2) NOT NULL DEFAULT 0"),
    ("packeta_packet_id", "varchar(100)"),
    ("packeta_tracking_number", "varchar(100)"),
    ("packeta_label_pdf", "varchar(100)"),
    ("packeta_created_at", "timestamp with time zone"),
    ("packeta_point_id", "varchar(100)"),
    ("packeta_point_name", "varchar(255)"),
    ("stock_reduced", "boolean NOT NULL DEFAULT false"),
]


def repair_schema(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FIX_SQL, params=None)
        return

    # Portable equivalent for SQLite (local `manage.py test`). Migrations 0004,
    # 0005, 0006, 0007, 0012 used SeparateDatabaseAndState(database_operations=[]),
    # so on a fresh database of ANY vendor these columns/the user_id nullability
    # change were only ever recorded in Django's migration state, never applied
    # physically. FIX_SQL's Postgres-only syntax has no SQLite equivalent, so
    # existence/nullability are checked in Python instead of SQL.
    table_name = "payments_order"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing = {
            column.name: column
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "stripe_payment_intend_id" in existing and "stripe_payment_intent_id" not in existing:
        schema_editor.execute(
            f"ALTER TABLE {table_name} RENAME COLUMN stripe_payment_intend_id TO stripe_payment_intent_id"
        )

    for column_name, ddl in SQLITE_MISSING_COLUMNS:
        if column_name not in existing:
            schema_editor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    user_id_column = existing.get("user_id")
    if user_id_column is not None and not user_id_column.null_ok:
        Order = apps.get_model("payments", "Order")
        new_field = Order._meta.get_field("user")
        old_field = copy.deepcopy(new_field)
        old_field.null = False
        schema_editor.alter_field(Order, old_field, new_field)


class Migration(migrations.Migration):
    """
    Bezpečná opravná migrace – přidá sloupce pouze pokud chybí.
    Na PostgreSQL (produkce/staging) je chování beze změny.
    Na SQLite (lokální testy) přidá stejné sloupce portable cestou.
    """

    dependencies = [
        ("payments", "0017_shopsettings"),
    ]

    operations = [
        migrations.RunPython(repair_schema, migrations.RunPython.noop),
    ]
