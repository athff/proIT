"""Transactional, create-only CSV import orchestration."""

from collections import Counter
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from .csv_base import CSVImportError, ImportErrorDetail, convert, model_errors, parse_csv
from .registry import ModelSpec, SPEC_BY_KEY


@dataclass(frozen=True)
class ImportResult:
    model: str
    total_rows: int
    created: int
    errors: tuple[ImportErrorDetail, ...] = ()


def _identity(row, spec: ModelSpec):
    return tuple(row.get(column) for column in spec.identity)


def _resolve(value, fk, row_number):
    if value is None:
        if fk.nullable:
            return None
        raise CSVImportError(
            [ImportErrorDetail(row_number, fk.column, "required", "Relationship is required.")]
        )
    filters = {field: value for field, value in zip(fk.lookup_columns, [value])}
    try:
        return fk.model.objects.get(**filters)
    except fk.model.DoesNotExist as exc:
        raise CSVImportError(
            [ImportErrorDetail(row_number, fk.column, "foreign_key_not_found", "Related record was not found.")]
        ) from exc
    except fk.model.MultipleObjectsReturned as exc:
        raise CSVImportError(
            [ImportErrorDetail(row_number, fk.column, "foreign_key_ambiguous", "Related record is ambiguous.")]
        ) from exc


def _prepare(content: bytes, spec: ModelSpec):
    raw_rows = parse_csv(content, spec)
    errors: list[ImportErrorDetail] = []
    prepared = []
    seen = Counter()
    for row_number, raw in raw_rows:
        try:
            row = {
                column.name: convert(raw[column.name], column, row_number)
                for column in spec.columns
                if column.name in raw
            }
            for fk in spec.foreign_keys:
                row[fk.column] = _resolve(row.get(fk.column), fk, row_number)
            if spec.key == "asset_models":
                row["manufacturer"] = _resolve(raw.get("manufacturer", "").strip(), spec.foreign_keys[0], row_number)
                row["category"] = _resolve(raw.get("category", "").strip(), spec.foreign_keys[1], row_number)
            if spec.key == "assets":
                row["model"] = _resolve_model(raw, row_number)
                if row["assigned_employee"] is not None and row["status"] != "assigned":
                    errors.append(ImportErrorDetail(row_number, "status", "assignment_status", "Assigned assets must use status assigned."))
                if row["status"] == "assigned" and row["assigned_employee"] is None:
                    errors.append(ImportErrorDetail(row_number, "assigned_employee", "assignment_status", "Assigned assets require an employee."))
            key = _identity(row, spec)
            identity_values = (
                [key]
                if spec.key == "asset_models"
                else [row.get(field) for field in spec.identity]
            )
            for identity_value in identity_values:
                seen[(spec.key, identity_value)] += 1
                if seen[(spec.key, identity_value)] > 1:
                    errors.append(
                        ImportErrorDetail(
                            row_number,
                            None,
                            "duplicate_file",
                            "Duplicate identity in file.",
                        )
                    )
            prepared.append((row_number, row, key))
        except CSVImportError as exc:
            errors.extend(exc.errors)
    if errors:
        raise CSVImportError(errors)
    for row_number, row, key in prepared:
        if _database_duplicate(row, spec):
            errors.append(ImportErrorDetail(row_number, None, "duplicate_database", "Record already exists."))
    if errors:
        raise CSVImportError(errors)
    return prepared


def _resolve_model(raw, row_number):
    from assets.models import AssetModel, Manufacturer
    try:
        manufacturer = Manufacturer.objects.get(name=raw.get("manufacturer", "").strip())
        return AssetModel.objects.get(manufacturer=manufacturer, name=raw.get("model", "").strip())
    except (Manufacturer.DoesNotExist, AssetModel.DoesNotExist) as exc:
        raise CSVImportError(
            [ImportErrorDetail(row_number, "model", "foreign_key_not_found", "Asset model was not found.")]
        ) from exc
    except AssetModel.MultipleObjectsReturned as exc:
        raise CSVImportError(
            [ImportErrorDetail(row_number, "model", "foreign_key_ambiguous", "Asset model is ambiguous.")]
        ) from exc


def _database_identity(row, spec):
    if spec.key == "asset_models":
        return {"manufacturer": row["manufacturer"], "name": row["name"]}
    return {field: row[field] for field in spec.identity if field in row}


def _database_duplicate(row, spec):
    if spec.key == "asset_models":
        return spec.model.objects.filter(
            manufacturer=row["manufacturer"], name=row["name"]
        ).exists()
    query = Q()
    for field in spec.identity:
        if field in row:
            query |= Q(**{field: row[field]})
    return spec.model.objects.filter(query).exists()


def import_csv(content: bytes, model_key: str) -> ImportResult:
    spec = SPEC_BY_KEY[model_key]
    prepared = _prepare(content, spec)
    objects = []
    for row_number, row, _ in prepared:
        obj = spec.build(row) if spec.build else spec.model(**row)
        try:
            obj.full_clean()
        except ValidationError as exc:
            raise CSVImportError(model_errors(exc, row_number)) from exc
        objects.append(obj)
    try:
        with transaction.atomic():
            for obj in objects:
                obj.save(force_insert=True)
    except IntegrityError as exc:
        raise CSVImportError(
            [ImportErrorDetail(0, None, "database_integrity", "Import was rolled back because a database constraint failed.")]
        ) from exc
    return ImportResult(model_key, len(objects), len(objects))


def import_bundle(files: dict[str, bytes]) -> tuple[ImportResult, ...]:
    results = []
    with transaction.atomic():
        for key in ("departments", "locations", "vendors", "categories", "manufacturers", "employees", "asset_models", "assets"):
            if key not in files:
                continue
            spec = SPEC_BY_KEY[key]
            prepared = _prepare(files[key], spec)
            objects = []
            for row_number, row, _ in prepared:
                obj = spec.build(row) if spec.build else spec.model(**row)
                try:
                    obj.full_clean()
                except ValidationError as exc:
                    raise CSVImportError(model_errors(exc, row_number)) from exc
                objects.append(obj)
            try:
                for obj in objects:
                    obj.save(force_insert=True)
            except IntegrityError as exc:
                raise CSVImportError(
                    [ImportErrorDetail(0, None, "database_integrity", "Bundle was rolled back because a constraint failed.")]
                ) from exc
            results.append(ImportResult(key, len(objects), len(objects)))
    return tuple(results)
