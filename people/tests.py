"""People app tests: Department, Location, and Employee models."""

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from dataio.services.authorization import IT_STAFF, VIEWER, configure_role_groups
from people.models import Department, Employee, Location


class DepartmentModelTest(TestCase):
    """Tests for the Department model."""

    def setUp(self):
        self.department = Department.objects.create(
            name="Engineering",
            description="Product engineering",
        )

    def test_department_creation_and_defaults(self):
        self.assertEqual(str(self.department), "Engineering")
        self.assertTrue(self.department.is_active)
        self.assertIsNotNone(self.department.created_at)

    def test_department_name_is_unique(self):
        with self.assertRaises(ValidationError):
            Department(name="Engineering").full_clean()

    def test_department_name_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            Department(name="   ").full_clean()

    def test_department_ordering(self):
        Department.objects.create(name="Zoology")
        Department.objects.create(name="Accounting")
        self.assertEqual(
            list(Department.objects.values_list("name", flat=True)),
            ["Accounting", "Engineering", "Zoology"],
        )

    def test_department_absolute_url(self):
        self.assertEqual(
            self.department.get_absolute_url(),
            f"/people/departments/{self.department.pk}/",
        )


class LocationModelTest(TestCase):
    """Tests for the Location model."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Main Office",
            city="London",
            country="United Kingdom",
        )

    def test_location_creation_and_defaults(self):
        self.assertEqual(str(self.location), "Main Office")
        self.assertTrue(self.location.is_active)
        self.assertIsNotNone(self.location.created_at)

    def test_location_name_is_unique(self):
        with self.assertRaises(ValidationError):
            Location(name="Main Office").full_clean()

    def test_location_name_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            Location(name="   ").full_clean()

    def test_location_ordering(self):
        Location.objects.create(name="Zeta Branch")
        Location.objects.create(name="Alpha Branch")
        self.assertEqual(
            list(Location.objects.values_list("name", flat=True)),
            ["Alpha Branch", "Main Office", "Zeta Branch"],
        )

    def test_location_absolute_url(self):
        self.assertEqual(
            self.location.get_absolute_url(),
            f"/people/locations/{self.location.pk}/",
        )


class EmployeeModelTest(TestCase):
    """Tests for the Employee model."""

    def setUp(self):
        self.department = Department.objects.create(name="Operations")
        self.location = Location.objects.create(name="Remote Office")
        self.employee = Employee.objects.create(
            employee_id="EMP-1001",
            first_name="Ada",
            last_name="Lovelace",
            email="ADA.LOVELACE@EXAMPLE.COM",
            department=self.department,
            location=self.location,
        )

    def test_employee_creation_and_defaults(self):
        self.assertEqual(str(self.employee), "EMP-1001: Ada Lovelace")
        self.assertTrue(self.employee.is_active)
        self.assertIsNotNone(self.employee.created_at)

    def test_employee_unique_identifiers(self):
        with self.assertRaises(ValidationError):
            Employee(
                employee_id="EMP-1001",
                first_name="Grace",
                last_name="Hopper",
                email="grace.hopper@example.com",
            ).full_clean()
        with self.assertRaises(ValidationError):
            Employee(
                employee_id="EMP-1002",
                first_name="Grace",
                last_name="Hopper",
                email="ADA.LOVELACE@EXAMPLE.COM",
            ).full_clean()

    def test_employee_names_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            Employee(
                employee_id="EMP-1002",
                first_name=" ",
                last_name="Hopper",
                email="grace.hopper@example.com",
            ).full_clean()
        with self.assertRaises(ValidationError):
            Employee(
                employee_id="EMP-1003",
                first_name="Grace",
                last_name=" ",
                email="grace.hopper@example.com",
            ).full_clean()

    def test_employee_ordering(self):
        Employee.objects.create(
            employee_id="EMP-1002",
            first_name="Zoe",
            last_name="Brown",
            email="zoe.brown@example.com",
        )
        Employee.objects.create(
            employee_id="EMP-1003",
            first_name="Alice",
            last_name="Brown",
            email="alice.brown@example.com",
        )
        self.assertEqual(
            list(Employee.objects.values_list("employee_id", flat=True)),
            ["EMP-1003", "EMP-1002", "EMP-1001"],
        )

    def test_employee_properties(self):
        self.assertEqual(self.employee.full_name, "Ada Lovelace")
        self.assertEqual(self.employee.display_name, "EMP-1001 - Ada Lovelace")

    def test_employee_absolute_url(self):
        self.assertEqual(
            self.employee.get_absolute_url(),
            f"/people/employees/{self.employee.pk}/",
        )

    def test_employee_email_is_normalized_on_save(self):
        self.assertEqual(self.employee.email, "ada.lovelace@example.com")

    def test_employee_foreign_keys_set_null_on_delete(self):
        self.department.delete()
        self.location.delete()
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.department)
        self.assertIsNone(self.employee.location)


class PeopleWorkspaceTests(TestCase):
    def setUp(self):
        configure_role_groups()
        self.operator = get_user_model().objects.create_user(
            username="people-operator",
            password="Initial-password-123",
            is_staff=True,
        )
        self.operator.groups.add(Group.objects.get(name=IT_STAFF))
        self.viewer = get_user_model().objects.create_user(
            username="people-viewer",
            password="Initial-password-123",
            is_staff=True,
        )
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        self.department = Department.objects.create(name="People Operations")
        self.location = Location.objects.create(name="People HQ", city="London")
        self.employee = Employee.objects.create(
            employee_id="EMP-PEOPLE-1",
            first_name="Grace",
            last_name="Hopper",
            email="grace.people@example.com",
            department=self.department,
            location=self.location,
        )

    def test_operator_can_crud_each_people_resource(self):
        self.client.force_login(self.operator)
        for resource in ("employees", "departments", "locations"):
            self.assertEqual(self.client.get(reverse("people:list", args=[resource])).status_code, 200)
        response = self.client.post(
            reverse("people:create", args=["employees"]),
            {
                "employee_id": "EMP-PEOPLE-2",
                "first_name": "Katherine",
                "last_name": "Johnson",
                "email": "katherine.people@example.com",
                "department": self.department.pk,
                "location": self.location.pk,
                "is_active": "on",
            },
        )
        created = Employee.objects.get(employee_id="EMP-PEOPLE-2")
        self.assertRedirects(response, reverse("people:detail", args=["employees", created.pk]))
        response = self.client.post(
            reverse("people:update", args=["employees", created.pk]),
            {
                "employee_id": "EMP-PEOPLE-2",
                "first_name": "Katherine",
                "last_name": "Updated",
                "email": "katherine.people@example.com",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("people:detail", args=["employees", created.pk]))
        response = self.client.post(reverse("people:delete", args=["employees", created.pk]))
        self.assertRedirects(response, reverse("people:list", args=["employees"]))
        self.assertFalse(Employee.objects.filter(pk=created.pk).exists())

    def test_search_filter_and_pagination_work(self):
        self.client.force_login(self.operator)
        Department.objects.create(name="Inactive People", is_active=False)
        response = self.client.get(reverse("people:list", args=["departments"]), {"q": "People Operations"})
        self.assertContains(response, "People Operations")
        self.assertNotContains(response, "Inactive People")
        response = self.client.get(reverse("people:list", args=["departments"]), {"active": "false"})
        self.assertContains(response, "Inactive People")
        for index in range(11):
            Department.objects.create(name=f"Department {index:02d}")
        response = self.client.get(reverse("people:list", args=["departments"]), {"page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_duplicate_employee_validation_is_rendered(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            reverse("people:create", args=["employees"]),
            {
                "employee_id": self.employee.employee_id,
                "first_name": "Duplicate",
                "last_name": "Employee",
                "email": "duplicate.people@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_viewer_can_view_but_cannot_mutate(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("people:list", args=["employees"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("people:detail", args=["employees", self.employee.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("people:create", args=["employees"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("people:update", args=["employees", self.employee.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("people:delete", args=["employees", self.employee.pk])).status_code, 403)

    def test_anonymous_users_are_redirected(self):
        response = self.client.get(reverse("people:list", args=["employees"]))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('people:list', args=['employees'])}")
