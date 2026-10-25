from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assets.models import Asset, AssetModel, Category, Manufacturer
from dataio.services.authorization import IT_STAFF, VIEWER, configure_role_groups
from people.models import Location


class ReportTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.user = get_user_model().objects.create_user(
            username="report-user", password="Initial-password-123", is_staff=True
        )
        self.user.groups.add(Group.objects.get(name=IT_STAFF))
        category = Category.objects.create(name="Report Laptops")
        manufacturer = Manufacturer.objects.create(name="Report Maker")
        model = AssetModel.objects.create(
            name="Report 14", manufacturer=manufacturer, category=category
        )
        location = Location.objects.create(name="Report HQ")
        Asset.objects.create(
            asset_tag="REPORT-1",
            serial_number="REPORT-SN-1",
            model=model,
            location=location,
            status=Asset.Status.AVAILABLE,
        )
        Asset.objects.create(
            asset_tag="REPORT-2",
            serial_number="REPORT-SN-2",
            model=model,
            location=location,
            status=Asset.Status.ASSIGNED,
        )

    def test_reports_use_database_summary_values(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports"))
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(response.context["assigned_count"], 0)
        self.assertEqual(response.context["available_count"], 1)
        self.assertContains(response, "Report Laptops")
        self.assertContains(response, "Report HQ")

    def test_viewer_can_read_reports_and_anonymous_is_redirected(self):
        viewer = get_user_model().objects.create_user(
            username="report-viewer", password="Initial-password-123", is_staff=True
        )
        viewer.groups.add(Group.objects.get(name=VIEWER))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("reports")).status_code, 200)
        self.client.logout()
        response = self.client.get(reverse("reports"))
        self.assertRedirects(response, "/accounts/login/?next=/reports/")
