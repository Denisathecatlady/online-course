from django.test import TestCase
from django.urls import reverse


class PublicPagesTests(TestCase):
    def test_trainings_page_renders(self):
        response = self.client.get(reverse("courses:trainings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Praktické tréninky pro klidnější soužití se psem")
        self.assertContains(response, "Individuální konzultace problémového chování psa")

    def test_about_us_page_renders(self):
        response = self.client.get(reverse("courses:about_us"))

        self.assertRedirects(response, reverse("courses:cemu_se_venujeme"))

    def test_about_subpages_render(self):
        for route_name in [
            "courses:cemu_se_venujeme",
            "courses:nase_filozofie",
            "courses:moje_vzdelani",
            "courses:muj_pribeh",
        ]:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)
