"""Safe standard-library CSV parsing and conversion helpers."""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .registry import Column, ModelSpec


@dataclass(frozen=True)
class ImportErrorDetail:
    row: int
    column: str | None
    code: str
    message: str


class CSVImportError(Exception):
    def __init__(self, errors: list[ImportErrorDetail]):
        self.errors = errors
        super().__init__("CSV import validation failed.")


def parse_bool(value: str, row: int, column: str) -> bool:
    if value.lower() not in {"true", "false"    }:
        raise CSVImportError(
            [ImportErrorDetail(row, column, "invalid_boolean", "Use true or false.")]
        )
    return value.lower() == "true"


def convert(value: str, column: Column, row: int):
    value = value.strip()
    if not value:
        if column.required or not column.nullable:
            raise CSVImportError(
                [ImportErrorDetail(row, column.name, "required", "Value is required.")]
            )
        return None
    if column.kind == "boolean":
        return parse_bool(value, row, column.name)
    if column.kind == "date":
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise CSVImportError(
                [ImportErrorDetail(row, column.name, "invalid_date", "Use YYYY-MM-DD.")]
            )
    if column.kind == "decimal":
        try:
            return Decimal(value)
        except InvalidOperation:
            raise CSVImportError(
                [ImportErrorDetail(row, column.name, "invalid_decimal", "Use a decimal value.")]
            )
    return value


def parse_csv(content: bytes, spec: ModelSpec) -> list[tuple[int, dict[str, str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError(
            [ImportErrorDetail(1, None, "encoding", "CSV must be UTF-8 encoded.")]
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    errors: list[ImportErrorDetail] = []
    if len(headers) != len(set(headers)):
        errors.append(ImportErrorDetail(1, None, "duplicate_header", "Headers must be unique."))
    expected = set(spec.headers)
    for header in headers:
        if header not in expected:
            errors.append(ImportErrorDetail(1, header, "unknown_column", "Column is not supported."))
    for column in spec.columns:
        if column.required and column.name not in headers:
            errors.append(ImportErrorDetail(1, column.name, "missing_column", "Required column is missing."))
    if errors:
        raise CSVImportError(errors)
    rows = []
    for row_number, raw in enumerate(reader, start=2):
        if None in raw:
            errors.append(ImportErrorDetail(row_number, None, "extra_columns", "Too many values."))
            continue
        rows.append((row_number, raw))
    if errors:
        raise CSVImportError(errors)
    return rows


def model_errors(exc: ValidationError, row: int) -> list[ImportErrorDetail]:
    details = []
    for field, messages in exc.message_dict.items():
        for message in messages:
            details.append(ImportErrorDetail(row, field, "validation", message))
    return details
