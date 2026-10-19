"""Transfer the existing local SQLite dataset into the configured PostgreSQL database."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db import models
from django.db.models import Model
from django.utils import timezone


TRANSFER_MODELS = (
    get_user_model(),
    Group,
    "people.Department",
    "people.Location",
    "people.Employee",
    "vendors.Vendor",
    "assets.Category",
    "assets.Manufacturer",
    "assets.AssetModel",
    "assets.Asset",
)
OPTIONAL_ACCOUNT_MODELS = (
    "account.EmailAddress",
    "socialaccount.SocialAccount",
)
BUSINESS_TABLES = (
    "auth_user",
    "auth_group",
    "people_department",
    "people_location",
    "people_employee",
    "vendors_vendor",
    "assets_category",
    "assets_manufacturer",
    "assets_assetmodel",
    "assets_asset",
    "account_emailaddress",
    "socialaccount_socialaccount",
)


def _resolve_model(model: type[Model] | str) -> type[Model]:
    if isinstance(model, str):
        return apps.get_model(model)
    return model


def _source_table(model: type[Model]) -> str:
    return model._meta.db_table


def _convert_value(model: type[Model], column: str, value: Any) -> Any:
    if value is None:
        return None
    field = next(
        (field for field in model._meta.concrete_fields if field.attname == column),
        None,
    )
    if field is None:
        return value
    converted = field.to_python(value)
    if isinstance(field, models.DateTimeField) and settings.USE_TZ and timezone.is_naive(converted):
        converted = timezone.make_aware(converted, timezone.get_default_timezone())
    return converted


class Command(BaseCommand):
    help = "Dry-run or transfer the local SQLite data into the configured PostgreSQL database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report the transfer without writing (the default).",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Write the validated SQLite dataset to PostgreSQL.",
        )
        parser.add_argument(
            "--source",
            default=None,
            help="Override the SQLite source path (normally BASE_DIR/db.sqlite3).",
        )

    def handle(self, *args, **options):
        if options["dry_run"] and options["execute"]:
            raise CommandError("Choose either --dry-run or --execute, not both.")
        source = Path(options["source"] or settings.BASE_DIR / "db.sqlite3").resolve()
        self._validate_source(source)
        self._validate_destination()

        with self._open_source(source) as source_db:
            inventory = self._source_inventory(source_db)
            self._validate_source_integrity(source_db)
            self._validate_destination_empty()
            self._report_plan(inventory, source)
            if not options["execute"]:
                self.stdout.write(self.style.SUCCESS("Dry run complete; no writes performed."))
                return

            backup = self._backup_source(source)
            self.stdout.write(f"SQLite backup created: {backup.name}")
            with transaction.atomic():
                self._transfer(source_db)
                self._update_sequences()
                self._validate_destination_counts(inventory)
                self._validate_destination_integrity()
            self.stdout.write(self.style.SUCCESS("SQLite transfer completed successfully."))

    def _validate_source(self, source: Path) -> None:
        if source != (Path(settings.BASE_DIR) / "db.sqlite3").resolve():
            raise CommandError("The transfer source must be BASE_DIR/db.sqlite3.")
        if not source.is_file():
            raise CommandError("The SQLite source database does not exist.")

    def _validate_destination(self) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("Transfer requires the configured PostgreSQL destination.")

    def _open_source(self, source: Path) -> sqlite3.Connection:
        database = sqlite3.connect(
            f"file:{source.as_posix()}?mode=ro",
            uri=True,
        )
        database.row_factory = sqlite3.Row
        return database

    def _source_inventory(self, source_db: sqlite3.Connection) -> dict[str, int]:
        inventory = {}
        models = tuple(_resolve_model(model) for model in TRANSFER_MODELS + OPTIONAL_ACCOUNT_MODELS)
        for model in models:
            table = _source_table(model)
            inventory[table] = source_db.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        inventory["django_site"] = source_db.execute(
            'SELECT COUNT(*) FROM "django_site"'
        ).fetchone()[0]
        return inventory

    def _validate_source_integrity(self, source_db: sqlite3.Connection) -> None:
        checks = {
            "assets_assetmodel": """
                SELECT COUNT(*) FROM assets_assetmodel am
                LEFT JOIN assets_category c ON c.id = am.category_id
                LEFT JOIN assets_manufacturer m ON m.id = am.manufacturer_id
                WHERE c.id IS NULL OR m.id IS NULL
            """,
            "assets_asset": """
                SELECT COUNT(*) FROM assets_asset a
                LEFT JOIN assets_assetmodel m ON m.id = a.model_id
                WHERE m.id IS NULL
            """,
            "assets_assignment": """
                SELECT COUNT(*) FROM assets_asset
                WHERE (status = 'assigned' AND assigned_employee_id IS NULL)
                   OR (status <> 'assigned' AND assigned_employee_id IS NOT NULL)
            """,
        }
        orphan_count = sum(source_db.execute(query).fetchone()[0] for query in checks.values())
        if orphan_count:
            raise CommandError("SQLite source contains invalid relationships or assignments.")

    def _validate_destination_empty(self) -> None:
        with connection.cursor() as cursor:
            for table in BUSINESS_TABLES:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                if cursor.fetchone()[0]:
                    raise CommandError(
                        "PostgreSQL already contains transferable records; aborting."
                    )

    def _report_plan(self, inventory: dict[str, int], source: Path) -> None:
        self.stdout.write(f"Source: {source.name}")
        self.stdout.write("Transfer plan: users, groups, group permissions, People, Vendors, Assets, "
                          "email addresses, social accounts, and reconciled Site.")
        self.stdout.write("Excluded: migrations, content types, generated permissions, sessions, and admin logs.")
        self.stdout.write("Source record totals: " + ", ".join(
            f"{table}={count}" for table, count in sorted(inventory.items())
        ))

    def _backup_source(self, source: Path) -> Path:
        backup_dir = Path(settings.BASE_DIR) / "backups"
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")
        backup = backup_dir / f"db.sqlite3.transfer-{stamp}.bak"
        shutil.copy2(source, backup)
        return backup

    def _rows(self, source_db: sqlite3.Connection, model: type[Model]) -> list[dict[str, Any]]:
        table = _source_table(model)
        rows = source_db.execute(f'SELECT * FROM "{table}"').fetchall()
        return [dict(row) for row in rows]

    def _objects(self, source_db: sqlite3.Connection, model: type[Model]) -> list[Model]:
        objects = []
        for row in self._rows(source_db, model):
            values = {
                field.attname: _convert_value(model, field.attname, row[field.attname])
                for field in model._meta.concrete_fields
            }
            objects.append(model(**values))
        return objects

    def _bulk_create_preserving_timestamps(
        self,
        source_db: sqlite3.Connection,
        model: type[Model],
    ) -> None:
        objects = self._objects(source_db, model)
        if not objects:
            return

        timestamp_fields = [
            field
            for field in model._meta.concrete_fields
            if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
        ]
        original_timestamps = {
            obj.pk: {field.attname: getattr(obj, field.attname) for field in timestamp_fields}
            for obj in objects
        }
        model.objects.bulk_create(objects, batch_size=500)
        if timestamp_fields:
            for obj in objects:
                for field in timestamp_fields:
                    setattr(obj, field.attname, original_timestamps[obj.pk][field.attname])
            model.objects.bulk_update(
                objects,
                [field.attname for field in timestamp_fields],
                batch_size=500,
            )

    def _transfer(self, source_db: sqlite3.Connection) -> None:
        user_model = get_user_model()
        ordered_models = [
            user_model,
            Group,
            apps.get_model("people", "Department"),
            apps.get_model("people", "Location"),
            apps.get_model("vendors", "Vendor"),
            apps.get_model("assets", "Category"),
            apps.get_model("assets", "Manufacturer"),
            apps.get_model("people", "Employee"),
            apps.get_model("assets", "AssetModel"),
            apps.get_model("assets", "Asset"),
        ]
        for model in ordered_models:
            self._bulk_create_preserving_timestamps(source_db, model)

        permission_map = {
            (permission.content_type.app_label, permission.content_type.model, permission.codename): permission
            for permission in Permission.objects.select_related("content_type")
        }
        source_permissions = source_db.execute("""
            SELECT g.name, ct.app_label, ct.model, p.codename
            FROM auth_group_permissions gp
            JOIN auth_group g ON g.id = gp.group_id
            JOIN auth_permission p ON p.id = gp.permission_id
            JOIN django_content_type ct ON ct.id = p.content_type_id
            ORDER BY g.name
        """).fetchall()
        for group_name, app_label, model_name, codename in source_permissions:
            permission = permission_map.get((app_label, model_name, codename))
            if permission is None:
                raise CommandError("A source group permission is missing in PostgreSQL.")
            Group.objects.get(name=group_name).permissions.add(permission)

        site_rows = self._rows(source_db, Site)
        if len(site_rows) > 1:
            raise CommandError("SQLite contains more than one Site record.")
        if site_rows:
            source_site = site_rows[0]
            destination_site, _ = Site.objects.get_or_create(
                pk=source_site["id"],
                defaults={"domain": source_site["domain"], "name": source_site["name"]},
            )
            if destination_site.domain != source_site["domain"] or destination_site.name != source_site["name"]:
                raise CommandError("The existing PostgreSQL Site record conflicts with SQLite.")

        for model_name in OPTIONAL_ACCOUNT_MODELS:
            model = _resolve_model(model_name)
            self._bulk_create_preserving_timestamps(source_db, model)

        self._copy_user_relationships(source_db)

    def _copy_user_relationships(self, source_db: sqlite3.Connection) -> None:
        groups = dict(Group.objects.values_list("name", "id"))
        for user_id, group_id in source_db.execute("SELECT user_id, group_id FROM auth_user_groups"):
            group_name = source_db.execute(
                "SELECT name FROM auth_group WHERE id = ?", (group_id,)
            ).fetchone()[0]
            get_user_model().objects.get(pk=user_id).groups.add(groups[group_name])

        permission_map = {
            (permission.content_type.app_label, permission.content_type.model, permission.codename): permission
            for permission in Permission.objects.select_related("content_type")
        }
        source_permissions = source_db.execute("""
            SELECT user_id, ct.app_label, ct.model, p.codename
            FROM auth_user_user_permissions up
            JOIN auth_permission p ON p.id = up.permission_id
            JOIN django_content_type ct ON ct.id = p.content_type_id
        """).fetchall()
        for user_id, app_label, model_name, codename in source_permissions:
            permission = permission_map.get((app_label, model_name, codename))
            if permission is None:
                raise CommandError("A source user permission is missing in PostgreSQL.")
            get_user_model().objects.get(pk=user_id).user_permissions.add(permission)

    def _update_sequences(self) -> None:
        with connection.cursor() as cursor:
            for model in tuple(_resolve_model(model) for model in TRANSFER_MODELS + OPTIONAL_ACCOUNT_MODELS) + (Site,):
                table = connection.ops.quote_name(model._meta.db_table)
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM " + table,
                    [model._meta.db_table],
                )

    def _validate_destination_counts(self, inventory: dict[str, int]) -> None:
        for model in tuple(_resolve_model(model) for model in TRANSFER_MODELS + OPTIONAL_ACCOUNT_MODELS) + (Site,):
            actual = model.objects.count()
            expected = inventory[model._meta.db_table]
            if actual != expected:
                raise CommandError(f"Transfer count mismatch for {model._meta.db_table}.")

    def _validate_destination_integrity(self) -> None:
        asset_model = apps.get_model("assets", "Asset")
        invalid = asset_model.objects.filter(
            status=asset_model.Status.ASSIGNED,
            assigned_employee__isnull=True,
        ).exists() or asset_model.objects.exclude(
            status=asset_model.Status.ASSIGNED,
        ).filter(assigned_employee__isnull=False).exists()
        if invalid:
            raise CommandError("Transferred asset assignment state is inconsistent.")
