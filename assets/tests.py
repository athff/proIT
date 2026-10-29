"""Assets app model tests."""

import base64
from io import BytesIO
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from assets.models import Asset, AssetModel, Category, Manufacturer, SupportTicket
from people.models import Department, Employee, Location
from vendors.models import Vendor

from dataio.services.authorization import (
    ADMINISTRATOR,
    IT_STAFF,
    VIEWER,
    configure_role_groups,
)


class AssetModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Laptops")
        self.manufacturer = Manufacturer.objects.create(name="Example Systems")
        self.asset_model = AssetModel.objects.create(
            name="ProBook 14",
            manufacturer=self.manufacturer,
            category=self.category,
        )
        self.vendor = Vendor.objects.create(
            company_name="Example Supplier",
            email="supplier@example.com",
        )
        self.location = Location.objects.create(name="Head Office")
        self.department = Department.objects.create(name="Engineering")
        self.employee = Employee.objects.create(
            employee_id="EMP-2001",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            department=self.department,
            location=self.location,
        )

    def asset(self, **overrides):
        values = {
            "asset_tag": "AST-2001",
            "serial_number": "SN-2001",
            "model": self.asset_model,
            "vendor": self.vendor,
            "location": self.location,
            "assigned_employee": self.employee,
            "purchase_date": date(2026, 1, 10),
            "purchase_cost": Decimal("1250.00"),
            "warranty_expiry": date(2029, 1, 10),
            "notes": "Issued for development work.",
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    def test_catalog_creation_defaults_and_strings(self):
        self.assertEqual(str(self.category), "Laptops")
        self.assertTrue(self.category.is_active)
        self.assertEqual(str(self.manufacturer), "Example Systems")
        self.assertEqual(str(self.asset_model), "Example Systems ProBook 14")
        self.assertTrue(self.asset_model.is_active)

    def test_asset_creation_and_defaults(self):
        asset = self.asset()
        self.assertEqual(str(asset), "AST-2001: Example Systems ProBook 14")
        self.assertEqual(asset.status, Asset.Status.AVAILABLE)
        self.assertIsNotNone(asset.created_at)

    def test_unique_catalog_and_asset_fields(self):
        with self.assertRaises(ValidationError):
            Category(name="Laptops").full_clean()
        with self.assertRaises(ValidationError):
            Manufacturer(name="Example Systems").full_clean()
        with self.assertRaises(ValidationError):
            AssetModel(
                name="ProBook 14",
                manufacturer=self.manufacturer,
                category=self.category,
            ).full_clean()
        self.asset()
        with self.assertRaises(ValidationError):
            Asset(
                asset_tag="AST-2001",
                serial_number="SN-2002",
                model=self.asset_model,
            ).full_clean()
        with self.assertRaises(ValidationError):
            Asset(
                asset_tag="AST-2002",
                serial_number="SN-2001",
                model=self.asset_model,
            ).full_clean()

    def test_validation_rejects_blank_names_and_invalid_cost_dates(self):
        with self.assertRaises(ValidationError):
            Category(name=" ").full_clean()
        with self.assertRaises(ValidationError):
            Manufacturer(name=" ").full_clean()
        with self.assertRaises(ValidationError):
            AssetModel(
                name=" ",
                manufacturer=self.manufacturer,
                category=self.category,
            ).full_clean()
        with self.assertRaises(ValidationError):
            Asset(
                asset_tag=" ",
                serial_number=" ",
                model=self.asset_model,
                purchase_cost=Decimal("-1.00"),
                purchase_date=date(2026, 2, 1),
                warranty_expiry=date(2026, 1, 1),
            ).full_clean()

    def test_asset_relationships_and_assignment(self):
        asset = self.asset(status=Asset.Status.ASSIGNED)
        self.assertEqual(asset.model, self.asset_model)
        self.assertEqual(asset.vendor, self.vendor)
        self.assertEqual(asset.location, self.location)
        self.assertEqual(asset.assigned_employee, self.employee)
        self.assertIn(asset, self.employee.assets.all())
        self.assertEqual(asset.status, Asset.Status.ASSIGNED)

    def test_asset_ordering(self):
        self.asset()
        self.asset(asset_tag="AST-2002", serial_number="SN-2002")
        self.asset(asset_tag="AST-2003", serial_number="SN-2003")
        self.assertEqual(
            list(Asset.objects.values_list("asset_tag", flat=True)),
            ["AST-2001", "AST-2002", "AST-2003"],
        )

    def test_nullable_relationships_set_null(self):
        asset = self.asset()
        self.vendor.delete()
        self.location.delete()
        self.employee.delete()
        asset.refresh_from_db()
        self.assertIsNone(asset.vendor)
        self.assertIsNone(asset.location)
        self.assertIsNone(asset.assigned_employee)


class AssetWorkspaceTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.user = get_user_model().objects.create_user(
            username="asset-operator",
            password="Initial-password-123",
            is_staff=True,
        )
        self.user.groups.add(Group.objects.get(name=IT_STAFF))
        self.viewer = get_user_model().objects.create_user(
            username="asset-viewer",
            password="Initial-password-123",
            is_staff=True,
        )
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        self.admin_user = get_user_model().objects.create_user(
            username="asset-admin",
            password="Initial-password-123",
            is_staff=True,
        )
        self.admin_user.groups.add(Group.objects.get(name=ADMINISTRATOR))
        self.category = Category.objects.create(name="Workspace Laptops")
        self.manufacturer = Manufacturer.objects.create(name="Workspace Maker")
        self.asset_model = AssetModel.objects.create(
            name="Workspace 14",
            manufacturer=self.manufacturer,
            category=self.category,
        )
        self.location = Location.objects.create(name="Workspace HQ")
        self.employee = Employee.objects.create(
            employee_id="EMP-WORKSPACE",
            first_name="Grace",
            last_name="Hopper",
            email="grace.workspace@example.com",
        )

    def asset(self, tag="WORK-001", serial="WORK-SN-001", **kwargs):
        return Asset.objects.create(
            asset_tag=tag,
            serial_number=serial,
            model=self.asset_model,
            location=self.location,
            **kwargs,
        )

    def test_operator_can_create_view_update_and_delete(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("assets:create"),
            {
                "asset_tag": "CRUD-001",
                "serial_number": "CRUD-SN-001",
                "model": self.asset_model.pk,
                "location": self.location.pk,
                "assigned_employee": self.employee.pk,
                "status": Asset.Status.ASSIGNED,
                "purchase_date": "2026-01-10",
                "purchase_cost": "1200.00",
                "warranty_expiry": "2029-01-10",
                "notes": "Created in workspace.",
            },
        )
        asset = Asset.objects.get(asset_tag="CRUD-001")
        self.assertRedirects(response, reverse("assets:detail", args=[asset.pk]))
        self.assertEqual(self.client.get(reverse("assets:detail", args=[asset.pk])).status_code, 200)
        response = self.client.post(
            reverse("assets:update", args=[asset.pk]),
            {
                "asset_tag": "CRUD-001",
                "serial_number": "CRUD-SN-001",
                "model": self.asset_model.pk,
                "status": Asset.Status.MAINTENANCE,
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry": "",
                "notes": "Updated.",
            },
        )
        self.assertRedirects(response, reverse("assets:detail", args=[asset.pk]))
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.Status.MAINTENANCE)
        response = self.client.post(reverse("assets:delete", args=[asset.pk]))
        self.assertRedirects(response, reverse("assets:list"))
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())

    def test_list_filters_search_and_pagination(self):
        self.asset()
        self.asset(tag="WORK-002", serial="WORK-SN-002", status=Asset.Status.MAINTENANCE)
        self.asset(tag="WORK-003", serial="WORK-SN-003", assigned_employee=self.employee)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("assets:list"),
            {"q": "WORK-002", "status": Asset.Status.MAINTENANCE},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WORK-002")
        self.assertNotContains(response, "WORK-001")
        response = self.client.get(reverse("assets:list"), {"assignment": "assigned"})
        self.assertContains(response, "WORK-003")
        self.assertNotContains(response, "WORK-001")
        response = self.client.get(reverse("assets:list"), {"q": "Workspace HQ"})
        self.assertContains(response, "WORK-001")
        response = self.client.get(reverse("assets:list"), {"q": "WORK-SN-002"})
        self.assertContains(response, "WORK-002")

    def test_operator_can_assign_and_return_asset(self):
        asset = self.asset()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("assets:assign"),
            {"asset": asset.pk, "employee": self.employee.pk},
        )
        self.assertRedirects(response, reverse("assets:detail", args=[asset.pk]))
        asset.refresh_from_db()
        self.assertEqual(asset.assigned_employee, self.employee)
        self.assertEqual(asset.status, Asset.Status.ASSIGNED)
        detail = self.client.get(reverse("assets:detail", args=[asset.pk]))
        self.assertContains(detail, "Grace Hopper")
        self.assertContains(detail, "Return asset")

        response = self.client.post(reverse("assets:return", args=[asset.pk]))
        self.assertRedirects(response, reverse("assets:detail", args=[asset.pk]))
        asset.refresh_from_db()
        self.assertIsNone(asset.assigned_employee)
        self.assertEqual(asset.status, Asset.Status.AVAILABLE)

    def test_assignment_rejects_ineligible_or_invalid_assets(self):
        assigned = self.asset(
            tag="WORK-004",
            serial="WORK-SN-004",
            assigned_employee=self.employee,
            status=Asset.Status.ASSIGNED,
        )
        maintenance = self.asset(
            tag="WORK-005",
            serial="WORK-SN-005",
            status=Asset.Status.MAINTENANCE,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("assets:assign"),
            {"asset": assigned.pk, "employee": self.employee.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        response = self.client.post(
            reverse("assets:assign"),
            {"asset": maintenance.pk, "employee": self.employee.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        response = self.client.post(
            reverse("assets:assign"),
            {"asset": self.asset().pk, "employee": 999999},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")

    def test_viewer_cannot_assign_or_return(self):
        asset = self.asset()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("assets:assign")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("assets:return", args=[asset.pk])).status_code,
            403,
        )

    def test_create_validation_rejects_duplicate_and_invalid_dates(self):
        self.asset()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("assets:create"),
            {
                "asset_tag": "WORK-001",
                "serial_number": "NEW-SN",
                "model": self.asset_model.pk,
                "purchase_date": "2026-02-01",
                "warranty_expiry": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asset with this Asset tag already exists")
        self.assertContains(response, "Warranty expiry cannot be before the purchase date.")

    def test_viewer_can_view_but_cannot_mutate(self):
        asset = self.asset()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("assets:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("assets:detail", args=[asset.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("assets:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("assets:update", args=[asset.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("assets:delete", args=[asset.pk])).status_code, 403)

    def test_anonymous_users_are_redirected(self):
        response = self.client.get(reverse("assets:list"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('assets:list')}")

    def test_administrator_can_generate_printable_qr_label(self):
        asset = self.asset()
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("assets:qr-label", args=[asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Print QR label")
        self.assertContains(response, asset.asset_tag)
        self.assertContains(response, asset.serial_number)
        self.assertContains(response, asset.model.name)
        self.assertEqual(
            response.context["qr_payload"],
            "\n".join(
                (
                    "PROIT ASSET",
                    f"Asset tag: {asset.asset_tag}",
                    f"Asset name: {asset.model}",
                    f"Serial number: {asset.serial_number}",
                )
            ),
        )
        image_data = response.context["qr_data_uri"].split(",", 1)[1]
        self.assertTrue(base64.b64decode(image_data).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_qr_label_is_restricted_to_administrators(self):
        asset = self.asset()
        url = reverse("assets:qr-label", args=[asset.pk])

        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_asset_detail_shows_qr_action_only_to_administrator(self):
        asset = self.asset()
        label_url = reverse("assets:qr-label", args=[asset.pk])

        self.client.force_login(self.admin_user)
        admin_response = self.client.get(reverse("assets:detail", args=[asset.pk]))
        self.assertContains(admin_response, label_url)
        self.assertContains(admin_response, "Print QR label")

        self.client.force_login(self.user)
        operator_response = self.client.get(reverse("assets:detail", args=[asset.pk]))
        self.assertNotContains(operator_response, label_url)


@override_settings(
    MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
)
class SupportTicketWorkflowTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.requester = get_user_model().objects.create_user(
            username="ticket-user",
            email="ticket.user@example.com",
            password="Initial-password-123",
        )
        self.admin_user = get_user_model().objects.create_superuser(
            username="ticket-admin",
            email="ticket.admin@example.com",
            password="Initial-password-123",
        )
        category = Category.objects.create(name="Ticket Laptops")
        manufacturer = Manufacturer.objects.create(name="Ticket Systems")
        model = AssetModel.objects.create(
            name="TicketBook 14",
            manufacturer=manufacturer,
            category=category,
        )
        employee = Employee.objects.create(
            employee_id="EMP-TICKET",
            first_name="Ticket",
            last_name="User",
            email=self.requester.email,
        )
        other_employee = Employee.objects.create(
            employee_id="EMP-OTHER",
            first_name="Other",
            last_name="User",
            email="other@example.com",
        )
        self.asset = Asset.objects.create(
            asset_tag="TICKET-001",
            serial_number="TICKET-SN-001",
            model=model,
            assigned_employee=employee,
            status=Asset.Status.ASSIGNED,
        )
        self.other_asset = Asset.objects.create(
            asset_tag="TICKET-002",
            serial_number="TICKET-SN-002",
            model=model,
            assigned_employee=other_employee,
            status=Asset.Status.ASSIGNED,
        )

    def test_user_can_raise_ticket_for_assigned_asset_and_receives_email(self):
        image_bytes = BytesIO()
        Image.new("RGB", (640, 360), "#17233f").save(image_bytes, format="PNG")
        attachment = SimpleUploadedFile(
            "screen.png",
            image_bytes.getvalue(),
            content_type="image/png",
        )
        self.client.force_login(self.requester)

        page = self.client.get(reverse("assets:ticket-create"))
        self.assertContains(page, self.asset.serial_number)
        self.assertNotContains(page, self.other_asset.serial_number)
        response = self.client.post(
            reverse("assets:ticket-create"),
            {
                "asset": self.asset.pk,
                "description": "The display is black after startup.",
                "priority": SupportTicket.Priority.CRITICAL,
                "attachment": attachment,
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        ticket = SupportTicket.objects.get(requester=self.requester)
        self.assertEqual(ticket.asset, self.asset)
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)
        self.assertTrue(ticket.attachment_data_uri.startswith("data:image/webp;base64,"))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(ticket.reference, mail.outbox[0].subject)
        self.assertTrue(mail.outbox[0].alternatives)

    def test_user_sees_only_own_tickets_and_cannot_open_admin_queue(self):
        own = SupportTicket.objects.create(
            requester=self.requester,
            asset=self.asset,
            description="Battery does not charge.",
        )
        other = SupportTicket.objects.create(
            requester=self.admin_user,
            asset=self.other_asset,
            description="Other issue.",
        )
        self.client.force_login(self.requester)

        response = self.client.get(reverse("assets:ticket-list"))
        self.assertContains(response, own.reference)
        self.assertNotContains(response, other.reference)
        self.assertEqual(self.client.get(reverse("assets:ticket-admin-list")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("assets:ticket-detail", args=[other.reference])).status_code,
            403,
        )

    def test_admin_can_filter_assign_resolve_and_notify_requester(self):
        ticket = SupportTicket.objects.create(
            requester=self.requester,
            asset=self.asset,
            description="System will not start.",
            priority=SupportTicket.Priority.HIGH,
        )
        self.client.force_login(self.admin_user)

        queue = self.client.get(
            reverse("assets:ticket-admin-list"),
            {"status": SupportTicket.Status.OPEN, "priority": SupportTicket.Priority.HIGH},
        )
        self.assertContains(queue, ticket.reference)
        response = self.client.post(
            reverse("assets:ticket-admin-detail", args=[ticket.reference]),
            {
                "status": SupportTicket.Status.RESOLVED,
                "assigned_to": self.admin_user.pk,
                "admin_notes": "Power adapter tested internally.",
                "resolution": "Replaced the failed power adapter.",
            },
        )

        self.assertRedirects(
            response,
            reverse("assets:ticket-admin-detail", args=[ticket.reference]),
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.RESOLVED)
        self.assertEqual(ticket.assigned_to, self.admin_user)
        self.assertIsNotNone(ticket.resolved_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Status updated", mail.outbox[0].subject)
