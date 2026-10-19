"""Centralized application roles and authorization policy."""

from collections.abc import Iterable

from django.contrib.auth.models import Group, Permission

ADMINISTRATOR = "Administrator"
IT_STAFF = "IT Staff"
VIEWER = "Viewer"
ROLE_NAMES = (ADMINISTRATOR, IT_STAFF, VIEWER)

DOMAIN_MODELS = (
    ("people", "department"),
    ("people", "location"),
    ("people", "employee"),
    ("vendors", "vendor"),
    ("assets", "category"),
    ("assets", "manufacturer"),
    ("assets", "assetmodel"),
    ("assets", "asset"),
)


def is_role(user, role: str) -> bool:
    return bool(
        user.is_authenticated
        and (user.is_superuser or user.groups.filter(name=role).exists())
    )


def has_managed_role(user) -> bool:
    return bool(
        user.is_authenticated
        and user.groups.filter(name__in=ROLE_NAMES).exists()
    )


def can_export(user, model) -> bool:
    permission = f"{model._meta.app_label}.view_{model._meta.model_name}"
    if is_role(user, ADMINISTRATOR):
        return True
    if is_role(user, IT_STAFF) or is_role(user, VIEWER):
        return user.has_perm(permission)
    return bool(user.is_staff and not has_managed_role(user) and user.has_perm(permission))


def can_import(user, model) -> bool:
    permission = f"{model._meta.app_label}.add_{model._meta.model_name}"
    if is_role(user, ADMINISTRATOR):
        return True
    if is_role(user, IT_STAFF):
        return user.has_perm(permission)
    return bool(user.is_staff and not has_managed_role(user) and user.has_perm(permission))


def can_view(user, model) -> bool:
    """Return whether a user may view records for a model."""
    return _can_model_action(user, model, "view")


def can_change(user, model) -> bool:
    """Return whether a user may edit records for a model."""
    return _can_model_action(user, model, "change")


def can_delete(user, model) -> bool:
    """Return whether a user may delete records for a model."""
    return _can_model_action(user, model, "delete")


def _can_model_action(user, model, action: str) -> bool:
    permission = f"{model._meta.app_label}.{action}_{model._meta.model_name}"
    if is_role(user, ADMINISTRATOR):
        return True
    if is_role(user, IT_STAFF) or is_role(user, VIEWER):
        return user.has_perm(permission)
    return bool(
        user.is_authenticated
        and user.is_staff
        and not has_managed_role(user)
        and user.has_perm(permission)
    )


def permissions_for_role(role: str) -> Iterable[Permission]:
    """Return the permissions that should be assigned to a managed role."""
    from django.contrib.contenttypes.models import ContentType

    domain_permissions = Permission.objects.filter(
        content_type__in=[
            ContentType.objects.get_by_natural_key(app_label, model)
            for app_label, model in DOMAIN_MODELS
        ]
    )
    if role == ADMINISTRATOR:
        auth_permissions = Permission.objects.filter(
            content_type__app_label="auth",
            content_type__model__in=("user", "group"),
        )
        return Permission.objects.filter(
            pk__in=domain_permissions.union(auth_permissions).values("pk")
        )
    if role == IT_STAFF:
        return domain_permissions
    if role == VIEWER:
        return domain_permissions.filter(codename__startswith="view_")
    raise ValueError(f"Unknown managed role: {role}")


def configure_role_groups() -> dict[str, Group]:
    """Create or refresh the three managed groups without duplicating them."""
    groups = {}
    for role in ROLE_NAMES:
        group, _ = Group.objects.get_or_create(name=role)
        group.permissions.set(permissions_for_role(role))
        groups[role] = group
    return groups
