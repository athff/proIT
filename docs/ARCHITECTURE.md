# Architecture

## Proposed Architecture Overview

This project follows a ** Django + Django REST Framework ** backend architecture with PostgreSQL as the data store. The design is modular, layered, and independent of any specific frontend.

## High-Level Design Principles

- **Independence**: No dependency on Snipe-IT code, branding, or proprietary assets
- **Modularity**: Each functional area is a separate Django app with clear boundaries
- **Testability**: All components designed for unit and integration testing
- **Extensibility**: New capabilities added via app addition, not monolith modifications
- **API-First**: Core business logic exposed via REST API; UI is secondary
- **PostgreSQL-native**: Leveraging PostgreSQL features (JSONB, constraints, triggers) where beneficial

## Module Boundaries

Each module is a Django app with a focused responsibility. The app structure is planned as follows:

| App Name | Primary Responsibility | Key Models |
|---|---|---|
| `assets` | Hardware assets and asset lifecycle | Asset, AssetType, AssetStatus, Accessory |
| `people` | Employees, departments, locations | Employee, Department, Location |
| `checkouts` | Asset checkout and check-in | Checkout, Checkin, CheckoutRequest |
| `accessories` | Accessories and consumables | Accessory, Consumable |
| `licenses` | Software licenses | License, SoftwareTitle |
| `vendors` | Vendors and maintenance | Vendor, MaintenanceContract, ServiceTicket |
| `reporting` | Auditing, reporting, notifications | AuditLog, Report, Notification, Setting |
| `api` | Authentication, permissions, integrations | APICredential, OAuthConfig, PermissionRule |

## Data Model Approach

- Models defined in each app's `models.py`
- Relationships use Django's ORM with `ForeignKey`, `ManyToManyField`, and `OneToOneField`
- Custom managers for common query patterns
- No raw SQL migrations required for initial setup; Django migrations handle schema evolution

## API Design

- **Endpoints** provided by Django REST Framework's `DefaultRouter` and `ViewSet` classes
- **Authentication**: Pluggable authentication backends (SessionAuthentication, TokenAuthentication, JWT)
- **Permissions**: Django REST Framework's permission classes; custom RBAC for resource-level access
- **Versioning**: API versioning supported via URL path or header (implemented in later phases)
- **Filtering**: django-filter integration for list endpoints
- **Pagination**: PageNumberPagination as default; configurable page sizes

## Storage and Media

- User-uploaded assets (screenshots, documentation, etc.) stored in `media/` directory
- Static files (CSS, JS) collected via `collectstatic`
- PostgreSQL stores metadata; media files stored on filesystem or cloud storage (configurable)

## Deployment Considerations

- Set `DJANGO_ENV=production` for deployed processes. Production startup fails
  when `SECRET_KEY` is missing/insecure, `DEBUG` is true, `ALLOWED_HOSTS` is
  empty,   or `PROIT_EMAIL_BACKEND` is Django's console backend.
- `DEBUG=False` and `ALLOWED_HOSTS` must be configured for production domains.
- Configure a non-console `PROIT_EMAIL_BACKEND` and protected SMTP/provider
  credentials so password-reset links are not written to logs.
- Enable HTTPS deployment protections (`SECURE_SSL_REDIRECT`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and appropriate HSTS settings)
  at the deployment layer after TLS is verified.
- `STATIC_ROOT` is `staticfiles/`; run `collectstatic` during deployment. Keep
  `SECURE_HSTS_SECONDS=0` until HTTPS is verified end-to-end, then configure
  trusted HTTPS origins and staged HSTS at the deployment layer.
- Database connection via environment variables (`DATABASE_URL`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)
- Static and media file storage configured for the target deployment environment
- Secret management via `.env` files; never committed to version control

## Module Interactions

- `people` app is referenced by `assets` (asset assigned to employee) and `checkouts` (checkout to/from employee)
- `vendors` app referenced by `assets` (purchase vendor) and `licenses` (software vendor)
- `reporting` app reads from all other apps for audit and summary data
- `api` app sits at the project level, providing authentication and base permissions