"""Role-based authorization tests for dataio operations."""

import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from people.models import Department

from .services.authorization import (
    ADMINISTRATOR,
    IT_STAFF,
    VIEWER,
    configure_role_groups,
)


class RoleAuthorizationTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.users = {}
        for role in (ADMINISTRATOR, IT_STAFF, VIEWER):
            user = get_user_model().objects.create_user(
                username=role.lower().replace(" ", "_"),
                password="Safe-password-123",
                is_staff=True,
            )
            user.groups.add(Group.objects.get(name=role))
            self.users[role] = user

    def test_setup_is_repeatable_without_duplicate_groups(self):
        configure_role_groups()
        self.assertEqual(Group.objects.filter(name=ADMINISTRATOR).count(), 1)
        self.assertEqual(Group.objects.filter(name=IT_STAFF).count(), 1)
        self.assertEqual(Group.objects.filter(name=VIEWER).count(), 1)

    def test_administrator_can_export_and_import(self):
        self.client.force_login(self.users[ADMINISTRATOR])
        export = self.client.get(reverse("csv-template", args=["departments"]))
        self.assertEqual(export.status_code, 200)
        upload = SimpleUploadedFile(
            "departments.csv",
            b"name,description,is_active\nOperations,,true\n",
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("csv-import", args=["departments"]), {"file": upload}
        )
        self.assertEqual(response.status_code, 200)

    def test_it_staff_can_export_and_import(self):
        self.client.force_login(self.users[IT_STAFF])
        self.assertEqual(
            self.client.get(reverse("csv-template", args=["departments"])).status_code,
            200,
        )
        upload = SimpleUploadedFile(
            "departments.csv",
            b"name,description,is_active\nSupport,,true\n",
            content_type="text/csv",
        )
        self.assertEqual(
            self.client.post(
                reverse("csv-import", args=["departments"]), {"file": upload}
            ).status_code,
            200,
        )

    def test_viewer_can_export_but_cannot_import(self):
        self.client.force_login(self.users[VIEWER])
        self.assertEqual(
            self.client.get(reverse("csv-template", args=["departments"])).status_code,
            200,
        )
        upload = SimpleUploadedFile(
            "departments.csv",
            b"name,description,is_active\nBlocked,,true\n",
            content_type="text/csv",
        )
        self.assertEqual(
            self.client.post(
                reverse("csv-import", args=["departments"]), {"file": upload}
            ).status_code,
            403,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("csv-template", args=["departments"]))
        self.assertRedirects(
            response,
            f"/accounts/login/?next=/dataio/template/departments/",
        )

    def test_superuser_preserves_full_access(self):
        user = get_user_model().objects.create_superuser(
            username="root",
            email="root@example.com",
            password="Safe-password-123",
        )
        self.client.force_login(user)
        self.assertEqual(
            self.client.get(reverse("csv-template", args=["departments"])).status_code,
            200,
        )
