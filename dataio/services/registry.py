"""CSV schemas and model mappings for the current domain models."""

from dataclasses import dataclass
from typing import Any, Callable

from assets.models import Asset, AssetModel, Category, Manufacturer
from people.models import Department, Employee, Location
from vendors.models import Vendor


@dataclass(frozen=True)
class Column:
    name: str
    required: bool = False
    nullable: bool = False
    kind: str = "text"


@dataclass(frozen=True)
class ForeignKeySpec:
    column: str
    model: type
    lookup_columns: tuple[str, ...]
    nullable: bool = True


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model: type
    columns: tuple[Column, ...]
    identity: tuple[str, ...]
    foreign_keys: tuple[ForeignKeySpec, ...] = ()
    select_related: tuple[str, ...] = ()
    build: Callable[[dict[str, Any]], Any] | None = None

    @property
    def headers(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


def build_asset_model(row):
    return AssetModel(
        name=row["name"],
        manufacturer=row["manufacturer"],
        category=row["category"],
        is_active=row.get("is_active", True),
    )


def build_asset(row):
    return Asset(
        asset_tag=row["asset_tag"],
        serial_number=row["serial_number"],
        model=row["model"],
        vendor=row["vendor"],
        location=row["location"],
        assigned_employee=row["assigned_employee"],
        status=row.get("status", Asset.Status.AVAILABLE),
        purchase_date=row.get("purchase_date"),
        purchase_cost=row.get("purchase_cost"),
        warranty_expiry=row.get("warranty_expiry"),
        notes=row.get("notes"),
    )


COMMON_ACTIVE = (Column("is_active", kind="boolean"),)

SPECS = (
    ModelSpec(
        "departments",
        Department,
        (Column("name", True), Column("description", nullable=True), *COMMON_ACTIVE),
        ("name",),
    ),
    ModelSpec(
        "locations",
        Location,
        (
            Column("name", True),
            Column("address", nullable=True),
            Column("city", nullable=True),
            Column("region", nullable=True),
            Column("country", nullable=True),
            *COMMON_ACTIVE,
        ),
        ("name",),
    ),
    ModelSpec(
        "vendors",
        Vendor,
        (
            Column("company_name", True),
            Column("contact_name", nullable=True),
            Column("email", nullable=True),
            Column("phone", nullable=True),
            Column("website", nullable=True),
            Column("address", nullable=True),
            Column("notes", nullable=True),
            *COMMON_ACTIVE,
        ),
        ("company_name",),
    ),
    ModelSpec(
        "categories",
        Category,
        (Column("name", True), Column("description", nullable=True), *COMMON_ACTIVE),
        ("name",),
    ),
    ModelSpec(
        "manufacturers",
        Manufacturer,
        (Column("name", True), Column("website", nullable=True), *COMMON_ACTIVE),
        ("name",),
    ),
    ModelSpec(
        "employees",
        Employee,
        (
            Column("employee_id", True),
            Column("first_name", True),
            Column("last_name", True),
            Column("email", True),
            Column("department", nullable=True),
            Column("location", nullable=True),
            *COMMON_ACTIVE,
        ),
        ("employee_id", "email"),
        (
            ForeignKeySpec("department", Department, ("name",)),
            ForeignKeySpec("location", Location, ("name",)),
        ),
        select_related=("department", "location"),
    ),
    ModelSpec(
        "asset_models",
        AssetModel,
        (
            Column("name", True),
            Column("manufacturer", True),
            Column("category", True),
            *COMMON_ACTIVE,
        ),
        ("manufacturer", "name"),
        (
            ForeignKeySpec("manufacturer", Manufacturer, ("name",), False),
            ForeignKeySpec("category", Category, ("name",), False),
        ),
        select_related=("manufacturer", "category"),
        build=build_asset_model,
    ),
    ModelSpec(
        "assets",
        Asset,
        (
            Column("asset_tag", True),
            Column("serial_number", True),
            Column("model", True),
            Column("manufacturer", True),
            Column("vendor", nullable=True),
            Column("location", nullable=True),
            Column("assigned_employee", nullable=True),
            Column("status", kind="status"),
            Column("purchase_date", nullable=True, kind="date"),
            Column("purchase_cost", nullable=True, kind="decimal"),
            Column("warranty_expiry", nullable=True, kind="date"),
            Column("notes", nullable=True),
        ),
        ("asset_tag", "serial_number"),
        (
            ForeignKeySpec("vendor", Vendor, ("company_name",)),
            ForeignKeySpec("location", Location, ("name",)),
            ForeignKeySpec("assigned_employee", Employee, ("employee_id",)),
        ),
        select_related=("model__manufacturer", "vendor", "location", "assigned_employee"),
        build=build_asset,
    ),
)

SPEC_BY_KEY = {spec.key: spec for spec in SPECS}
SPEC_BY_MODEL = {spec.model: spec for spec in SPECS}
