# KaziForce

A capstone implementation of **Profile and Skills Evaluation Using TF-IDF and Cosine Similarity for Candidate-Job Matching**

The application uses **Python, Django, PostgreSQL on Neon, NLTK, scikit-learn, ESCO, HTML, CSS and JavaScript**. `psycopg` is Django's PostgreSQL driver. No frontend framework, transformer, external AI service, model training or alternative database is used. Dependencies brought in by those packages are their supporting libraries.

`requirements-lock.txt` records the exact versions verified for this build. Use it in place of `requirements.txt` when you want to reproduce the same environment.

## Run on this computer

Open a VS Code terminal in this project folder and run:

```powershell
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/**. Keep the terminal open while using the app. Press **Ctrl+C** to stop it. The web app runs on your computer; data is stored in your online Neon PostgreSQL database. An internet connection is required.

If demo data has been created, open `.local/demo-accounts.txt` locally for candidate, recruiter and administrator credentials. These are generated randomly and excluded from Git. All demo people, organisations and roles are explicitly fictional. You can also register your own account at `/register/`.

## Fresh installation

Python 3.13 was used for this build. In PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

On its first run, the bootstrap script creates `.venv` and `.env`, installs the exact
locked dependencies, and generates a private secret. Add the Neon `DATABASE_URL` to
`.env`, then run the same command again to check the database, apply migrations,
prepare NLTK and validate Django. Use `-SkipNlp` on later runs when those resources
are already present.

The equivalent manual setup is:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe scripts/prepare_env.py
```

Edit `.env` and set `DATABASE_URL` to your Neon connection string. It must start with `postgresql://` and include `sslmode=require`. Paste the URL only, without `psql` or Markdown backslashes. Never commit this file or paste the password into a public issue.

```powershell
.venv\Scripts\python.exe manage.py check_database
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py setup_nlp
```

Download the English ESCO catalogue using the included Windows downloader. Windows may block PowerShell script files; the following sets an override for this command only, without changing the system policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/download_esco.ps1 -PageSize 500
.venv\Scripts\python.exe manage.py import_esco data/esco-skill-en.csv --occupations data/esco-occupation-en.csv --esco-version 1.2.0
```

The API downloader explicitly requests ESCO v1.2.0, an available API version. It stores official English labels, alternative labels, concept URIs, descriptions and a provenance record. To use a different official release, download its English CSV package from [ESCO](https://esco.ec.europa.eu/en/use-esco/download) and import `skills_en.csv` and `occupations_en.csv` with the corresponding `--esco-version`. The importer updates existing concept URIs and preserves job relationships. It does not automatically delete retired concepts.

Restart the web server after importing a catalogue update. The application reuses the ESCO index and NLTK resources between requests; the first matching request in a new process is slower while these load.

For a small demonstration (three candidates, two jobs and one application):

```powershell
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py runserver
```

For an installation without demo data, create your administrator interactively instead:

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

## Features

| Candidate | Recruiter | Administrator |
| --- | --- | --- |
| Register, sign in, change password | Register and manage organisation | Manage users and roles |
| Manage skills, qualifications, certifications, experience, portfolio | Create and edit job postings, draft/open/closed states | Moderate job postings |
| Attach PDF, DOCX or TXT resume | Choose ESCO skills and priorities 1–5 | Inspect and manage ESCO concepts |
| Automatic TXT/DOCX text extraction | Set essential skill requirements | Inspect saved matching results |
| Top 10 open job recommendations | Top 10 eligible candidates per job | Inspect application history |
| Explained scores and skill gaps | Download rankings as CSV | Use Django's administration interface |
| Apply, track status and withdraw | Review, shortlist and record hiring decisions | |

PDF attachments are stored securely and downloaded through access checks. **Automatic PDF text extraction is not implemented in the application**, because the specified stack does not include a PDF parser. Paste PDF text into “Resume text for matching”, or enter the relevant information in the profile fields. The development-only `pypdf` package was used to read the proposal and is not an application dependency.

## Verification and evaluation

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test recruitment --noinput
```

For the complete repeatable check (tests, migration drift and Django system checks), run:

```powershell
.venv\Scripts\python.exe scripts/verify.py
```

GitHub Actions runs the same verification on pushes and pull requests with an isolated
PostgreSQL service. See `CONTRIBUTING.md` for the branch, review and definition-of-done
workflow.

Django creates a separate `test_kaziforce` PostgreSQL database and removes it after tests. `manage.py test` automatically uses `config.test_settings`, which connects to Neon's direct endpoint so pooled sessions cannot block cleanup. The database role needs permission to create test databases. Do not run simultaneous test processes against the same test database.

For research evaluation, have reviewers label candidate-job pairs in the CSV format shown in `data/evaluation-labels.example.csv`. Grades are 0 (irrelevant) through 3 (highly relevant). Separate expected missing ESCO skill URIs with `|`; use `[]` for no missing skills.

```powershell
.venv\Scripts\python.exe manage.py evaluate_matching data/evaluation-labels.csv --threshold 50
```

This writes measured Precision@10, NDCG@10, threshold accuracy, skill-gap F1 and response time to `docs/evaluation-results.json`. The score threshold is an evaluation choice, not a hiring rule. Human-labelled accuracy and user acceptance results must come from actual evaluation, not demo data.

## Documentation

- `docs/requirements.md`: source-to-feature mapping and implementation decisions.
- `docs/architecture.md`: domain model, database relationships, matching formula and workflows.
- `docs/user-manual.md`: candidate, recruiter and administrator walkthroughs.
- `docs/neon-setup.md`: online database setup and troubleshooting.
- `docs/testing-and-evaluation.md`: executed checks and UAT protocol.

## Deployment boundary

This is the proposal's controlled capstone prototype. The database is online; the website is not publicly hosted by this setup. Django's development server is for local demonstrations. Before a public deployment, configure HTTPS, `DJANGO_DEBUG=False`, a unique secret, allowed hosts and trusted origins, serve collected static files and private media correctly, and use an appropriate production Python server. Hosting infrastructure and additional server packages were not added to your specified application stack.

The matching engine processes an in-memory corpus for each ranking request. It fits IDF over the compared documents without supervised training. This suits the controlled prototype, not millions of profiles. Scores describe textual evidence; they do not verify qualifications, infer ability or make automated hiring decisions.


