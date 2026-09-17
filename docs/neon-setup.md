# Neon PostgreSQL setup

1. Sign in at https://console.neon.tech and choose **New project**.
2. Name the project **KaziForce** and select a supported PostgreSQL version, cloud provider and region. Region refers to the database's physical location; it does not restrict where you can connect from. Use a region close to the eventual application server. The supplied US East connection also works from Kenya.
3. Open **Connect**, select the database and role, and copy the PostgreSQL URL. A pooled connection works with this configuration.
4. Copy `.env.example` to `.env` if `.env` does not exist. Preserve any existing generated `DJANGO_SECRET_KEY`.
5. Set `DATABASE_URL` to the copied URL. Do not include a leading `psql`, enclosing quotes, or Markdown escape characters. Keep `sslmode=require` and `channel_binding=require` when supplied by Neon.
6. Run `.venv\Scripts\python.exe scripts/prepare_env.py` to replace the example secret with a secure random secret.
7. Run `.venv\Scripts\python.exe manage.py check_database`. The check prints connection success and client TLS status without the password.
8. Run `.venv\Scripts\python.exe manage.py migrate` to create the tables.
9. Start the application with `.venv\Scripts\python.exe manage.py runserver`.

The app uses PostgreSQL exclusively. There is no SQLite fallback. Django parses the URL using Python's standard library; the PostgreSQL driver is psycopg. Connections may be reused for 60 seconds (`CONN_MAX_AGE=60`), with `CONN_HEALTH_CHECKS=True` to check a reused connection before a request. Server-side cursors are disabled for the Neon pooler. Online connections reject SSL modes weaker than `require`.

If the role password changes, copy the updated URL from Neon into `.env` and restart Django. Since the original connection string was shared in chat, rotate that password in Neon before using the system with real candidate information, then update `.env`.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Could not connect | Check internet access, Neon project status, the host and the current password. |
| Invalid PostgreSQL URL | Remove `psql`, quotes and Markdown backslashes. Confirm the database name appears after the host. |
| Tables do not exist | Run `manage.py migrate` against the same `.env` used by the server. |
| First connection is slow | Neon may need to resume the compute endpoint. Retry once it is available. |
| Browser refuses a form | Use `http://127.0.0.1:8000` with local `DJANGO_DEBUG=True`. For production, configure the HTTPS host and `CSRF_TRUSTED_ORIGINS`. |
| Tests cannot create a database | Use a development PostgreSQL role with database-creation permission. Never point destructive test setup at the application database. |

Credentials are stored only in `.env`, which Git ignores. This workspace is under OneDrive; its existing sync settings also apply to local files.

References: [Neon Python connection guide](https://neon.com/docs/guides/python), [Django PostgreSQL database settings](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes).
