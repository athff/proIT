"""Vendors app tests: Vendor model tests."""

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from dataio.services.authorization import IT_STAFF, VIEWER, configure_role_groups

from vendors.models import Vendor


class VendorModelTest(TestCase):
    """Tests for the Vendor model."""

    def test_vendor_creation(self):
        """Test basic vendor creation."""
        vendor = Vendor.objects.create(
            company_name="Acme Corp",
            contact_name="John Doe",
            email="contact@acme.com",
        )
        self.assertEqual(str(vendor), "Acme Corp")
        self.assertTrue(vendor.is_active)
        self.assertIsNotNone(vendor.created_at)

    def test_vendor_company_name_unique(self):
        """Test that vendor company name must be unique."""
        Vendor.objects.create(
            company_name="Acme Corp",
            contact_name="John Doe",
            email="contact@acme.com",
        )
        with self.assertRaises(ValidationError):
            Vendor(company_name="Acme Corp").full_clean()

    def test_vendor_company_name_blank_invalid(self):
        """Test that vendor company name cannot be blank."""
        vendor = Vendor(company_name="")
        with self.assertRaises(ValidationError):
            vendor.full_clean()

    def test_vendor_is_active_default(self):
        """Test that is_active defaults to True."""
        vendor = Vendor.objects.create(
            company_name="Globex Corp",
            email="info@globex.com",
        )
        self.assertTrue(vendor.is_active)

    def test_vendor_ordering(self):
        """Test that vendors are ordered by company name."""
        Vendor.objects.create(company_name="Zeta Inc", email="zeta@inc.com")
        Vendor.objects.create(company_name="Alpha Corp", email="alpha@inc.com")
        vendors = Vendor.objects.all()
        self.assertEqual(vendors[0].company_name, "Alpha Corp")

    def test_vendor_get_absolute_url(self):
        """Test get_absolute_url is defined."""
        vendor = Vendor.objects.create(
            company_name="Beta Corp",
            email="beta@corp.com",
        )
        url = vendor.get_absolute_url()
        self.assertIn("/vendors/vendors/", url)

    def test_vendor_email_normalization(self):
        """Test that email is normalized to lowercase."""
        vendor = Vendor.objects.create(
            company_name="Test Corp",
            email="UPPERCASE@EXAMPLE.COM",
        )
        vendor.full_clean()  # Normalize email
        self.assertEqual(vendor.email, "uppercase@example.com")

    def test_vendor_without_contact(self):
        """Test vendor without contact name."""
        vendor = Vendor.objects.create(
            company_name="No Contact Corp",
            email="nocontact@example.com",
        )
        self.assertIsNone(vendor.contact_name)

    def test_vendor_without_email(self):
        """Test vendor without email (not unique constraint)."""
        vendor = Vendor.objects.create(
            company_name="No Email Corp",
        )
        self.assertIsNone(vendor.email)


class VendorWorkspaceTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.operator = get_user_model().objects.create_user(
            username="vendor-operator",
            password="Initial-password-123",
            is_staff=True,
        )
        self.operator.groups.add(Group.objects.get(name=IT_STAFF))
        self.viewer = get_user_model().objects.create_user(
            username="vendor-viewer",
            password="Initial-password-123",
            is_staff=True,
        )
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        self.vendor = Vendor.objects.create(
            company_name="Workspace Supplier",
            contact_name="Taylor Vendor",
            email="workspace.vendor@example.com",
            phone="+44 20 5555 1234",
            website="https://supplier.example.com",
            address="1 Supplier Street",
            notes="Preferred supplier",
        )

    def test_operator_can_create_view_update_and_delete_vendor(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("vendors:create"),
            {
                "company_name": "New Workspace Supplier",
                "contact_name": "Alex Contact",
                "email": "new.supplier@example.com",
                "phone": "+44 20 5555 9999",
                "website": "https://new.example.com",
                "address": "2 Supplier Street",
                "notes": "New supplier",
                "is_active": "on",
            },
        )
        vendor = Vendor.objects.get(company_name="New Workspace Supplier")
        self.assertRedirects(response, reverse("vendors:detail", args=[vendor.pk]))
        self.assertEqual(self.client.get(reverse("vendors:detail", args=[vendor.pk])).status_code, 200)
        response = self.client.post(
            reverse("vendors:update", args=[vendor.pk]),
            {
                "company_name": "Updated Workspace Supplier",
                "email": "updated.supplier@example.com",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("vendors:detail", args=[vendor.pk]))
        vendor.refresh_from_db()
        self.assertEqual(vendor.company_name, "Updated Workspace Supplier")
        response = self.client.post(reverse("vendors:delete", args=[vendor.pk]))
        self.assertRedirects(response, reverse("vendors:list"))
        self.assertFalse(Vendor.objects.filter(pk=vendor.pk).exists())

    def test_vendor_list_search_filter_and_pagination(self):
        Vendor.objects.create(company_name="Inactive Supplier", is_active=False)
        self.client.force_login(self.operator)
        response = self.client.get(reverse("vendors:list"), {"q": "Workspace"})
        self.assertContains(response, "Workspace Supplier")
        self.assertNotContains(response, "Inactive Supplier")
        response = self.client.get(reverse("vendors:list"), {"active": "false"})
        self.assertContains(response, "Inactive Supplier")
        for index in range(11):
            Vendor.objects.create(company_name=f"Supplier {index:02d}")
        response = self.client.get(reverse("vendors:list"), {"page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_duplicate_and_invalid_vendor_data_is_rejected(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("vendors:create"),
            {
                "company_name": self.vendor.company_name,
                "email": "not-an-email",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertContains(response, "Enter a valid email address")

    def test_viewer_can_view_but_cannot_mutate(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("vendors:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("vendors:detail", args=[self.vendor.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("vendors:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("vendors:update", args=[self.vendor.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("vendors:delete", args=[self.vendor.pk])).status_code, 403)

    def test_anonymous_users_are_redirected(self):
        response = self.client.get(reverse("vendors:list"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('vendors:list')}")