from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import UserProfile


class UserRoleTests(TestCase):
    def test_new_user_gets_user_role(self):
        user = get_user_model().objects.create_user(
            username="customer",
            email="customer@example.com",
            password="testpass123",
        )

        self.assertEqual(user.profile.role, UserProfile.Role.USER)
        self.assertFalse(user.is_staff)

    def test_admin_role_enables_staff_access(self):
        user = get_user_model().objects.create_user(
            username="admin-role",
            email="admin-role@example.com",
            password="testpass123",
        )

        user.profile.role = UserProfile.Role.ADMIN
        user.profile.save()
        user.refresh_from_db()

        self.assertTrue(user.is_staff)

    def test_user_role_disables_staff_access_for_non_superuser(self):
        user = get_user_model().objects.create_user(
            username="regular-role",
            email="regular-role@example.com",
            password="testpass123",
            is_staff=True,
        )

        user.profile.role = UserProfile.Role.USER
        user.profile.save()
        user.refresh_from_db()

        self.assertFalse(user.is_staff)
