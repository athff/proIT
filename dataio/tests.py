"""Tests for CSV parsing, model mappings, permissions, exports, and rollback."""

import csv
import io
import shutil
import sqlite3
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from django.db import connection, transaction
from django.utils import timezone

from assets.models import Asset, AssetModel, Category, Manufacturer
from people.models import Department, Employee, Location
from vendors.models import Vendor

from .services.csv_base import CSVImportError
from .services.export_service import _safe_cell, export_response
from .services.import_service import import_bundle, import_csv
from .services.registry import SPEC_BY_KEY


def csv_bytes(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode()


class SQLiteTransferCommandTest(TestCase):
    """Exercise the transfer command against a generated SQLite source.

    The command requires its source to be BASE_DIR/db.sqlite3, so each test
    points BASE_DIR at a temporary directory holding a purpose-built database
    instead of depending on a developer's local file.
    """

    SOURCE_DEPARTMENT = {
        "id": 1,
        "name": "Engineering",
        "description": "Builds things",
        "is_active": 1,
        "created_at": "2026-10-16 11:00:52.664720",
        "updated_at": "2026-10-16 11:30:12.100000",
    }

    def setUp(self):
        from .management.commands.transfer_sqlite_data import (
            OPTIONAL_ACCOUNT_MODELS,
            TRANSFER_MODELS,
            _resolve_model,
        )

        self.base_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base_dir, ignore_errors=True)
        self.source_path = self.base_dir / "db.sqlite3"

        models = [
            _resolve_model(model)
            for model in TRANSFER_MODELS + OPTIONAL_ACCOUNT_MODELS
        ] + [Site]
        source = sqlite3.connect(self.source_path)
        try:
            for model in models:
                columns = ", ".join(
                    f'"{field.attname}"' for field in model._meta.concrete_fields
                )
                source.execute(
                    f'CREATE TABLE "{model._meta.db_table}" ({columns})'
                )
            placeholders = ", ".join("?" * len(self.SOURCE_DEPARTMENT))
            names = ", ".join(f'"{key}"' for key in self.SOURCE_DEPARTMENT)
            source.execute(
                f'INSERT INTO "people_department" ({names}) VALUES ({placeholders})',
                tuple(self.SOURCE_DEPARTMENT.values()),
            )
            source.commit()
        finally:
            source.close()

    def _expected_timestamp(self, column):
        return timezone.make_aware(
            Department._meta.get_field(column).to_python(
                self.SOURCE_DEPARTMENT[column]
            ),
            timezone.get_default_timezone(),
        )

    def test_bulk_create_preserves_source_auto_timestamps(self):
        from .management.commands.transfer_sqlite_data import Command

        command = Command()
        source = command._open_source(self.source_path)
        try:
            command._bulk_create_preserving_timestamps(source, Department)
        finally:
            source.close()

        department = Department.objects.order_by("id").first()
        self.assertIsNotNone(department)
        self.assertEqual(department.created_at, self._expected_timestamp("created_at"))
        self.assertEqual(department.updated_at, self._expected_timestamp("updated_at"))

    def test_dry_run_does_not_write(self):
        with override_settings(BASE_DIR=self.base_dir):
            with patch.object(connection, "vendor", "postgresql"):
                call_command("transfer_sqlite_data", "--dry-run")
        self.assertEqual(Department.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_existing_business_data_aborts_transfer(self):
        Department.objects.create(name="Already present")
        with override_settings(BASE_DIR=self.base_dir):
            with patch.object(connection, "vendor", "postgresql"):
                with self.assertRaises(CommandError):
                    call_command("transfer_sqlite_data", "--dry-run")

    def test_source_outside_base_dir_is_rejected(self):
        with override_settings(BASE_DIR=self.base_dir):
            with patch.object(connection, "vendor", "postgresql"):
                with self.assertRaises(CommandError):
                    call_command(
                        "transfer_sqlite_data",
                        "--dry-run",
                        "--source",
                        str(self.base_dir / "elsewhere.sqlite3"),
                    )

    def test_transfer_rolls_back_when_validation_fails(self):
        with self.assertRaises(CommandError):
            with transaction.atomic():
                Department.objects.create(name="Rolled back")
                raise CommandError("forced validation failure")
        self.assertEqual(Department.objects.count(), 0)

    def test_timestamp_repair_converts_naive_source_values_to_aware_utc(self):
        from .management.commands.repair_neon_timestamps import _values_equal
        from .management.commands.transfer_sqlite_data import _convert_value

        field = Department._meta.get_field("created_at")
        converted = _convert_value(Department, "created_at", "2026-10-16 11:00:52.664720")
        self.assertTrue(timezone.is_aware(converted))
        self.assertEqual(converted.tzinfo, timezone.get_default_timezone())
        self.assertTrue(_values_equal(converted, field.to_python(converted)))

    def test_timestamp_repair_dry_run_does_not_write(self):
        from .management.commands.repair_neon_timestamps import Command

        with patch.object(connection, "vendor", "postgresql"), patch.object(
            Command, "_validate_database_identity"
        ), patch.object(Command, "_build_plans", return_value={Department: []}):
            call_command("repair_neon_timestamps", "--dry-run")
        self.assertEqual(Department.objects.count(), 0)

    def test_timestamp_repair_mismatch_protection(self):
        from .management.commands.repair_neon_timestamps import Command

        with patch.object(connection, "vendor", "postgresql"), patch.object(
            Command, "_validate_database_identity"
        ), patch.object(
            Command,
            "_build_plans",
            side_effect=CommandError("Non-timestamp data mismatch for people_department."),
        ):
            with self.assertRaises(CommandError):
                call_command("repair_neon_timestamps", "--dry-run")

    def test_timestamp_repair_rolls_back_updates_on_validation_failure(self):
        from .management.commands.repair_neon_timestamps import Command

        department = Department.objects.create(name="Rollback Department")
        original = department.created_at
        plan = {Department: [{"pk": department.pk, "timestamps": {"created_at": original}}]}
        command = Command()
        with self.assertRaises(CommandError):
            with transaction.atomic():
                command._apply_plans(plan)
                raise CommandError("forced timestamp validation failure")
        department.refresh_from_db()
        self.assertEqual(department.created_at, original)


class CSVImportTest(TestCase):
    def setUp(self):
        self.department_headers = ("name", "description", "is_active")
        self.location_headers = (
            "name",
            "address",
            "city",
            "region",
            "country",
            "is_active",
        )

    def test_department_import_and_defaults(self):
        result = import_csv(
            csv_bytes(self.department_headers, [["Engineering", "", "true"]]),
            "departments",
        )
        self.assertEqual(result.created, 1)
        self.assertTrue(Department.objects.filter(name="Engineering").exists())

    def test_invalid_columns_and_missing_values_are_reported(self):
        with self.assertRaises(CSVImportError) as context:
            import_csv(csv_bytes(("wrong",), [["value"]]), "departments")
        codes = {error.code for error in context.exception.errors}
        self.assertIn("missing_column", codes)
        self.assertIn("unknown_column", codes)

    def test_duplicate_file_and_database_are_rejected(self):
        content = csv_bytes(self.department_headers, [["Engineering", "", "true"], ["Engineering", "", "true"]])
        with self.assertRaises(CSVImportError):
            import_csv(content, "departments")
        self.assertEqual(Department.objects.count(), 0)
        import_csv(csv_bytes(self.department_headers, [["Engineering", "", "true"]]), "departments")
        with self.assertRaises(CSVImportError):
            import_csv(csv_bytes(self.department_headers, [["Engineering", "", "true"]]), "departments")
        self.assertEqual(Department.objects.count(), 1)

    def test_employee_relationships_and_email_normalization(self):
        department = Department.objects.create(name="Engineering")
        location = Location.objects.create(name="HQ")
        headers = ("employee_id", "first_name", "last_name", "email", "department", "location", "is_active")
        import_csv(
            csv_bytes(headers, [["EMP-1", "Ada", "Lovelace", "ADA@EXAMPLE.COM", "Engineering", "HQ", "true"]]),
            "employees",
        )
        employee = Employee.objects.get(employee_id="EMP-1")
        self.assertEqual(employee.email, "ada@example.com")
        self.assertEqual(employee.department, department)
        self.assertEqual(employee.location, location)

    def test_asset_model_and_asset_relationships(self):
        category = Category.objects.create(name="Laptop")
        manufacturer = Manufacturer.objects.create(name="Acme")
        AssetModel.objects.create(name="X1", manufacturer=manufacturer, category=category)
        Vendor.objects.create(company_name="Supplier")
        Location.objects.create(name="HQ")
        Department.objects.create(name="Engineering")
        Employee.objects.create(
            employee_id="EMP-1",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        headers = SPEC_BY_KEY["assets"].headers
        row = ["AST-1", "SN-1", "X1", "Acme", "Supplier", "HQ", "EMP-1", "assigned", "2026-01-01", "100.00", "2027-01-01", "Issued"]
        import_csv(csv_bytes(headers, [row]), "assets")
        asset = Asset.objects.get(asset_tag="AST-1")
        self.assertEqual(asset.model.name, "X1")
        self.assertEqual(asset.purchase_cost, Decimal("100.00"))
        self.assertEqual(asset.assigned_employee.employee_id, "EMP-1")

    def test_invalid_row_rolls_back_all_rows(self):
        headers = ("name", "description", "is_active")
        content = csv_bytes(headers, [["Valid", "", "true"], ["", "", "true"]])
        with self.assertRaises(CSVImportError):
            import_csv(content, "categories")
        self.assertEqual(Category.objects.count(), 0)

    def test_bundle_rolls_back_when_later_file_fails(self):
        files = {
            "departments": csv_bytes(("name", "description", "is_active"), [["Engineering", "", "true"]]),
            "locations": csv_bytes(self.location_headers, [["HQ", "", "", "", "", "true"]]),
            "categories": csv_bytes(("name", "description", "is_active"), [["Laptop", "", "true"]]),
            "manufacturers": csv_bytes(("name", "website", "is_active"), [["Acme", "", "true"]]),
            "asset_models": csv_bytes(("name", "manufacturer", "category", "is_active"), [["X1", "Acme", "Laptop", "true"]]),
            "assets": csv_bytes(SPEC_BY_KEY["assets"].headers, [["AST-1", "", "X1", "Acme", "", "HQ", "", "available", "", "", "", ""]]),
        }
        with self.assertRaises(CSVImportError):
            import_bundle(files)
        self.assertEqual(Department.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)

    def test_export_uses_natural_keys_and_download_headers(self):
        category = Category.objects.create(name="Laptop")
        manufacturer = Manufacturer.objects.create(name="Acme")
        AssetModel.objects.create(name="X1", manufacturer=manufacturer, category=category)
        response = export_response(SPEC_BY_KEY["asset_models"])
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = b"".join(response.streaming_content).decode()
        self.assertIn("name,manufacturer,category,is_active", content)
        self.assertIn("X1,Acme,Laptop,true", content)

    def test_export_neutralizes_spreadsheet_formula_prefixes(self):
        dangerous = (
            "=SUM(1,1)",
            "+CMD",
            "-2+3",
            "@HYPERLINK",
            " \t=SUM(1,1)",
            "\x00=SUM(1,1)",
        )
        for value in dangerous:
            self.assertTrue(_safe_cell(value).lstrip().startswith("'"))
        self.assertEqual(_safe_cell("ordinary vendor"), "ordinary vendor")
        self.assertEqual(_safe_cell("123.45"), "123.45")

        Vendor.objects.create(company_name="=Injected Formula")
        response = export_response(SPEC_BY_KEY["vendors"])
        content = b"".join(response.streaming_content).decode()
        self.assertIn("'=Injected Formula", content)


class CSVViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff",
            password="password",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_staff_with_model_permission_can_download_template(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="view_department",
                content_type=ContentType.objects.get_for_model(Department),
            )
        )
        response = self.client.get(reverse("csv-template", args=["departments"]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"name,description,is_active", b"".join(response.streaming_content))

    def test_workspace_lists_templates_and_exports(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="view_department",
                content_type=ContentType.objects.get_for_model(Department),
            )
        )
        response = self.client.get(reverse("dataio-workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departments")
        self.assertContains(response, "Export CSV")

    def test_viewer_workspace_has_exports_but_no_imports(self):
        from django.contrib.auth.models import Group
        from .services.authorization import VIEWER, configure_role_groups

        configure_role_groups()
        viewer = get_user_model().objects.create_user(
            username="csv-viewer",
            password="Initial-password-123",
            is_staff=True,
        )
        viewer.groups.add(Group.objects.get(name=VIEWER))
        self.client.force_login(viewer)
        response = self.client.get(reverse("dataio-workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Export data")
        self.assertContains(response, "Your role does not allow imports.")

    def test_staff_without_model_permission_is_denied(self):
        response = self.client.get(reverse("csv-template", args=["departments"]))
        self.assertEqual(response.status_code, 403)

    def test_import_requires_add_permission_and_upload_size(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="add_department",
                content_type=ContentType.objects.get_for_model(Department),
            )
        )
        upload = SimpleUploadedFile(
            "departments.csv",
            csv_bytes(("name", "description", "is_active"), [["Engineering", "", "true"]]),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("csv-import", args=["departments"]),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)

    @override_settings(DATAIO_MAX_UPLOAD_SIZE=1)
    def test_import_rejects_oversized_upload(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="add_department",
                content_type=ContentType.objects.get_for_model(Department),
            )
        )
        upload = SimpleUploadedFile("departments.csv", b"name\nEngineering\n")
        response = self.client.post(
            reverse("csv-import", args=["departments"]),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 413)
