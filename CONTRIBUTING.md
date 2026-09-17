# Contributing to KaziForce

## Development workflow

1. Create a focused branch from the current default branch.
2. Keep credentials, uploaded resumes, generated catalogues and local reports out of Git.
3. Make a small, reviewable change and add or update tests for changed behaviour.
4. Run `.venv\Scripts\python.exe scripts\verify.py` before committing.
5. Use a concise imperative commit message, for example `Add candidate export validation`.
6. Open a pull request and wait for the continuous-integration check to pass before merging.

## Code organisation

- Put database entities and constraints in `recruitment/models.py` and migrations.
- Put request validation and form behaviour in `recruitment/forms.py`.
- Put HTTP orchestration and permission checks in `recruitment/views.py`.
- Keep ranking and text-processing logic in `recruitment/matching.py`.
- Put repeatable operational tasks in Django management commands or `scripts/`.
- Update the relevant file in `docs/` when behaviour or setup changes.

## Definition of done

A change is complete when its behaviour is tested, migrations are consistent, Django's
system check passes, user-facing documentation is current, and no secret or generated
artifact appears in `git status`.
