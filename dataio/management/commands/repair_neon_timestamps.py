"""Repair transferred PostgreSQL timestamps from the read-only SQLite source."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db import models
from django.db.models import Model
from django.utils import timezone

from .transfer_sqlite_data import _convert_value


EXPECTED_DATABASE = "neondb"
REPAIR_MODELS = (
    "people.Department",
    "people.Location",
    "people.Employee",
    "vendors.Vendor",
    "assets.Category",
    "assets.Manufacturer",
    "assets.AssetModel",
    "assets.Asset",
    "socialaccount.SocialAccount",
)


def _resolve_model(model_name: str) -> type[Model]:
    return apps.get_model(model_name)


def _timestamp_fields(model: type[Model]) -> tuple[models.DateTimeField, ...]:
    return tuple(
        field
        for field in model._meta.concrete_fields
        if isinstance(field, models.DateTimeField)
        and field.attname in {"created_at", "updated_at", "date_joined", "last_login"}
    )


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        return Decimal(str(left)) == Decimal(str(right))
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    if isinstance(left, datetime) and isinstance(right, datetime):
        if timezone.is_naive(left):
            left = timezone.make_aware(left, timezone.get_default_timezone())
        if timezone.is_naive(right):
            right = timezone.make_aware(right, timezone.get_default_timezone())
        return left == right
    return left == right


class Command(BaseCommand):
    help = "Repair transferred Neon timestamps from the local SQLite source."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report without writing (the default).",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Write validated timestamp corrections to PostgreSQL.",
        )

    def handle(self, *args, **options):
        if options["dry_run"] and options["execute"]:
            raise CommandError("Choose either --dry-run or --execute, not both.")

        source = (Path(settings.BASE_DIR) / "db.sqlite3").resolve()
        if not source.is_file():
            raise CommandError("The SQLite source database does not exist.")
        if connection.vendor != "postgresql":
            raise CommandError("Timestamp repair requires the configured PostgreSQL destination.")
        self._validate_database_identity()

        with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as source_db:
            source_db.row_factory = sqlite3.Row
            plans = self._build_plans(source_db)
            if not options["execute"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dry run complete; {sum(len(plan) for plan in plans.values())} "
                        "timestamp records validated; no writes performed."
                    )
                )
                return

            with transaction.atomic():
                self._apply_plans(plans)
                self._validate_repaired_rows(plans)

        self.stdout.write(self.style.SUCCESS("Neon timestamp repair completed successfully."))

    def _validate_database_identity(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
        if database != EXPECTED_DATABASE:
            raise CommandError("Connected PostgreSQL database is not the expected Neon database.")

    def _build_plans(self, source_db: sqlite3.Connection) -> dict[type[Model], list[dict[str, Any]]]:
        plans: dict[type[Model], list[dict[str, Any]]] = {}
        for model_name in REPAIR_MODELS:
            model = _resolve_model(model_name)
            timestamps = _timestamp_fields(model)
            source_rows = source_db.execute(
                f'SELECT * FROM "{model._meta.db_table}"'
            ).fetchall()
            destination = model.objects.in_bulk()
            if len(source_rows) != len(destination):
                raise CommandError(f"Record count mismatch for {model._meta.db_table}.")

            model_plan = []
            for source_row in source_rows:
                primary_key = source_row[model._meta.pk.attname]
                destination_object = destination.get(primary_key)
                if destination_object is None:
                    raise CommandError(f"Primary-key mismatch for {model._meta.db_table}.")
                for field in model._meta.concrete_fields:
                    if field in timestamps:
                        continue
                    source_value = _convert_value(model, field.attname, source_row[field.attname])
                    destination_value = getattr(destination_object, field.attname)
                    if not _values_equal(source_value, destination_value):
                        raise CommandError(
                            f"Non-timestamp data mismatch for {model._meta.db_table}."
                        )
                model_plan.append(
                    {
                        "pk": primary_key,
                        "timestamps": {
                            field.attname: _convert_value(
                                model, field.attname, source_row[field.attname]
                            )
                            for field in timestamps
                        },
                    }
                )
            plans[model] = model_plan
        return plans

    def _apply_plans(self, plans: dict[type[Model], list[dict[str, Any]]]) -> None:
        for model, model_plan in plans.items():
            for row in model_plan:
                model.objects.filter(pk=row["pk"]).update(**row["timestamps"])

    def _validate_repaired_rows(self, plans: dict[type[Model], list[dict[str, Any]]]) -> None:
        for model, model_plan in plans.items():
            for row in model_plan:
                destination = model.objects.get(pk=row["pk"])
                for field_name, expected in row["timestamps"].items():
                    actual = getattr(destination, field_name)
                    if not _values_equal(expected, actual):
                        raise CommandError(f"Timestamp validation failed for {model._meta.db_table}.")
