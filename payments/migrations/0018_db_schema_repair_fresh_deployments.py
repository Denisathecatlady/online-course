"""
Opravná migrace pro čerstvé databáze (staging, nová produkce).

Migrace 0004, 0005, 0006, 0007, 0012 používaly SeparateDatabaseAndState
s database_operations=[] a spoléhaly na to, že stávající produkční DB
sloupce již obsahuje. Na čerstvé PostgreSQL DB tyto sloupce chybí.

Tato migrace přidá všechny chybějící sloupce pomocí IF NOT EXISTS,
takže je bezpečná pro:
  - staging / nové nasazení (přidá chybějící sloupce)
  - produkci (IF NOT EXISTS je no-op, žádná data se nezmění)
"""

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

REVERSE_SQL = migrations.RunSQL.noop


class Migration(migrations.Migration):
    """
    Bezpečná opravná migrace – přidá sloupce pouze pokud chybí.
    Na produkci je kompletní no-op.
    """

    dependencies = [
        ("payments", "0017_shopsettings"),
    ]

    operations = [
        migrations.RunSQL(FIX_SQL, reverse_sql=REVERSE_SQL),
    ]
