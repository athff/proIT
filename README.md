# proIT

ProIT is a Django-based IT Asset Management application for managing assets,
employees, locations, departments, vendors, assignments, authentication, and
role-based access.

## Local development

Requirements: Python 3.11+ and Git.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

Local development uses SQLite when `DATABASE_URL` is absent or SQLite-based.
The real `.env` file, databases, backups, and virtual environments are ignored
by Git and must not be committed.

## Render deployment

The repository includes [render.yaml](render.yaml) and [build.sh](build.sh).
The Render build:

1. Installs `requirements.txt`.
2. Runs `python manage.py collectstatic --no-input`.

It does not run migrations or create a database. The start command is:

```text
gunicorn config.wsgi:application
```

Configure these Render environment variables without committing their values:

- `DJANGO_ENV=production`
- `DEBUG=False`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DATABASE_URL` — the existing Neon PostgreSQL connection string
- `PROIT_EMAIL_BACKEND` and provider-specific email settings
- `CSRF_TRUSTED_ORIGINS`
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when Google sign-in is enabled

Do not replace the existing `DATABASE_URL` with a newly provisioned database.
Review the service settings, configure HTTPS, and run migrations as a separate,
explicit release step only after the deployment target has been reviewed.

## Verification

```powershell
$env:DATABASE_URL = "sqlite:///db.sqlite3"
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture and
deployment considerations.
