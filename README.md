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

`DJANGO_ENV=production` and a stable `SECRET_KEY` are required on Vercel.
When `DJANGO_ENV` is omitted, the application detects Vercel's runtime
variables and defaults to production mode rather than generating a
per-process development key. Vercel hostnames are automatically added to
`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

For Gmail, enable 2-Step Verification on the sending Google account, create
an App Password under Google Account security, and use that 16-character App
Password as `EMAIL_HOST_PASSWORD`. Do not use the normal Gmail account
password, and do not commit the App Password.

Do not replace the existing `DATABASE_URL` with a newly provisioned database.
Review the service settings, configure HTTPS, and run migrations as a separate,
explicit release step only after the deployment target has been reviewed.

## Vercel deployment

Vercel provides native Django support through its Python runtime. This project
does not need a `vercel.json`, a serverless wrapper, or a Gunicorn start command
for Vercel. Vercel detects `manage.py`, reads
`WSGI_APPLICATION = "config.wsgi.application"`, installs
`requirements.txt`, runs `collectstatic`, and serves the Django WSGI
application as a Vercel Function. The existing `render.yaml` and `build.sh`
remain unchanged for Render.

### Import the GitHub repository

1. Create the GitHub repository and push this project using the existing
   `master` branch.
2. In Vercel, select **Add New Project**, choose **Import Git Repository**, and
   authorize access to the repository.
3. Select the ProIT repository and keep the repository root as the project
   root. Do not add a framework-specific serverless entrypoint.
4. Deploy only after adding the environment variables below.

### Vercel environment variables

Set these variables in the Vercel project for **Production**, **Preview**, or
both as appropriate. Enter values through Vercel's environment-variable
settings; never commit them.

- `DJANGO_ENV=production`
- `DEBUG=False`
- `SECRET_KEY` — a strong random production value
- `ALLOWED_HOSTS` — custom deployment hostname(s), comma-separated. Vercel's
  `VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL`, and `VERCEL_BRANCH_URL` are
  also accepted automatically.
- `CSRF_TRUSTED_ORIGINS` — HTTPS origins such as
  `https://your-project.vercel.app`, comma-separated
- `DATABASE_URL` — the existing Neon PostgreSQL connection string
- `PROIT_EMAIL_BACKEND` — a non-console backend in production
- Gmail SMTP variables:
  `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_HOST_USER`,
  `EMAIL_HOST_PASSWORD` (a Gmail App Password, not the normal account
  password), `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`, `EMAIL_TIMEOUT=30`,
  and `DEFAULT_FROM_EMAIL`. TLS and SSL must not both be enabled.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when Google sign-in is enabled

The application keeps PostgreSQL SSL enabled by default
(`sslmode=require`) and does not provision or replace the existing Neon
database. Run schema migrations as a separate, explicitly reviewed operation;
they are not part of the Vercel deployment configuration.

### Vercel verification

After the first deployment:

1. Confirm the build log reports successful dependency installation and static
   collection.
2. Open `/accounts/login/` and confirm the health check, login page, CSS, and
   logo load.
3. Test login, dashboard access, asset listing, employee details, assignment,
   CSV import/export permissions, password reset delivery, and Google OAuth
   callbacks if enabled.
4. Review function logs for database connection errors and confirm the
   application is using the existing Neon database.
5. Run migrations only through a reviewed release procedure, never by adding
   them to a build command.

### Vercel limitations

- Django runs as a Vercel Function rather than a persistent VM. Do not rely on
  process-local state, long-running workers, cron-like background work, or
  persistent in-process caches.
- Neon is the persistent database. Vercel functions may scale across
  instances, so database operations should remain short and connections should
  not be treated as permanently warm.
- Vercel serves collected static files through its CDN. The configured
  `STATIC_ROOT` and production WhiteNoise manifest backend are supported; no
  local static filesystem should be treated as durable runtime storage.
- This application accepts CSV uploads in request memory for import. Uploaded
  files are not stored as durable media. Any future user-uploaded media must
  use object storage or another persistent service.
- Function duration, memory, and request-size limits are Vercel plan/runtime
  concerns. Large imports and long reports should be tested against the
  selected Vercel plan before production use.

## Verification

```powershell
$env:DATABASE_URL = "sqlite:///db.sqlite3"
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture and
deployment considerations.
