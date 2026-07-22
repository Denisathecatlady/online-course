"""
Testy pro payments/services/heureka.py – bez reálného API klíče se integrace
musí chovat neškodně (jen loguje, nic neodesílá).
"""

from unittest.mock import patch

from django.test import TestCase, override_settings

from payments.models import Order
from payments.services.heureka import send_order_review_request


class HeurekaServiceTests(TestCase):

    def setUp(self):
        self.order = Order.objects.create(
            buyer_email="zakaznik@example.com",
            first_name="Jana",
            last_name="Dvořáková",
        )

    @override_settings(HEUREKA_API_KEY="", HEUREKA_ENABLED=False)
    def test_no_op_when_api_key_missing(self):
        """Bez HEUREKA_API_KEY se nic neodešle a funkce vrátí False."""
        with patch("payments.services.heureka.requests.post") as mock_post:
            with self.assertLogs("payments.services.heureka", level="INFO") as logs:
                result = send_order_review_request(self.order)

        self.assertFalse(result)
        mock_post.assert_not_called()
        self.assertTrue(any("Přeskočeno" in message for message in logs.output))

    @override_settings(HEUREKA_API_KEY="test-key", HEUREKA_ENABLED=True)
    def test_no_op_when_email_missing(self):
        """Bez e-mailu zákazníka se nic neodešle, i když je integrace zapnutá."""
        self.order.buyer_email = ""
        self.order.save(update_fields=["buyer_email"])

        with patch("payments.services.heureka.requests.post") as mock_post:
            result = send_order_review_request(self.order)

        self.assertFalse(result)
        mock_post.assert_not_called()

    @override_settings(HEUREKA_API_KEY="test-key", HEUREKA_ENABLED=True)
    def test_sends_request_when_enabled(self):
        """Se zapnutou integrací se odešle POST s e-mailem a číslem objednávky."""
        with patch("payments.services.heureka.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            result = send_order_review_request(self.order)

        self.assertTrue(result)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["email"], "zakaznik@example.com")
        self.assertEqual(kwargs["data"]["orderId"], str(self.order.id))
        self.assertEqual(kwargs["data"]["key"], "test-key")
