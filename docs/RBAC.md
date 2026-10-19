# proIT role-based access control

proIT uses Django's built-in `Group` and `Permission` models. The employee
record in `people.Employee` remains separate from the Django authentication
user account.

## Managed roles

Run this command after migrations, and whenever role permissions need to be
refreshed:

```powershell
python manage.py setup_roles
```

The command is safe to run repeatedly. It creates or refreshes exactly these
groups without creating duplicates:

### Administrator

- Full permissions for People, Vendors, and Assets models.
- Django User and Group permissions for account and role administration.
- Allowed to export, download templates, and import CSV data.
- A user must also be `is_staff=True` to access the Django admin site.
- Superusers retain access regardless of group membership.

### IT Staff

- Add, view, change, and delete permissions for People, Vendors, and Assets.
- Allowed to export, download templates, and import CSV data.
- No Django User or Group administration permissions.

### Viewer

- View-only permissions for People, Vendors, and Assets.
- Allowed to export data and download templates.
- CSV imports are denied.
- No create, update, or delete permissions.

## CSV authorization

CSV endpoints enforce the policy server-side:

- `GET /dataio/export/<model_key>/`: Administrator, IT Staff, Viewer.
- `GET /dataio/template/<model_key>/`: Administrator, IT Staff, Viewer.
- `POST /dataio/import/<model_key>/`: Administrator and IT Staff only.

Users must be authenticated. Anonymous users are redirected to the configured
login page. Authenticated users without the required role or model permission
receive HTTP 403.

The setup command assigns model permissions for all current People, Vendors,
and Assets models. It does not add permissions for future apps automatically;
the policy should be updated when new application domains are introduced.
