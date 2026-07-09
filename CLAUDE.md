# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup on a new machine

```bash
git clone https://github.com/FilippoBuffa/Sito_Sofia.git
cd Sito_Sofia
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env: set SECRET_KEY, MAIL_USERNAME, MAIL_PASSWORD, APP_BASE_URL, PORT
# (PORT only if 8080 is already taken on this machine — keep APP_BASE_URL in sync with it)

python3.10 run.py        # creates instance/app.db, runs migrations-less seed on first run
```

`instance/app.db` and `uploads/` (real user data — result files, DB rows) are **not** in git; they're excluded on purpose (see `.gitignore`). Copy them over separately (e.g. `scp`/`rsync`/USB) from the old machine if you need the existing data — otherwise the app starts with just the two seed accounts below.

If migrating an existing `instance/app.db` to a fresh checkout, run `flask db upgrade` (with `FLASK_APP=run.py` exported) instead of relying on `seed_db()`, so any migrations added after the DB was copied get applied.

## Running the app

```bash
python3.10 run.py        # seeds DB on first run, starts on port $PORT or 8080 (0.0.0.0)
```

Port 5000 is reserved by the system. Defaults to **8080** (`host=0.0.0.0`), overridable per-machine via `PORT` in `.env` (e.g. if 8080 is already used by another app on that host — keep `APP_BASE_URL` in sync so email links point to the right port). On this machine it's reachable at `http://10.10.11.11:8080`.

## Dev credentials

Login is by **email**, not username.

| Role     | Email               | Password   |
|----------|---------------------|------------|
| Client   | `admin@vernay.com`    | `admin`    |
| Engineer | `test_eng@vernay.com` | `test_eng` |

## Managing accounts (CLI only — no admin UI)

- Add an engineer: `python3.10 create_engineer.py` — prompts for name/email/services, emails a temp password.
- Delete an account: `python3.10 delete_user.py` — lists all accounts, refuses to delete one with linked requests/comments (would leave orphaned FK references since SQLite FK enforcement isn't enabled) unless run with `--force`.

## Architecture

Flask application using the **app factory pattern** (`create_app()` in `app/__init__.py`).

**Blueprints** (`app/blueprints/`):
- `auth` — login/logout
- `client` — dashboard, test catalog, new request form, request detail
- `engineer` — dashboard, request detail with accept/return/close actions

**Models** (`app/models/`):
- `User` + `TestService` — users have a role (`client`/`engineer`); engineers are linked to services via `engineer_services` M2M table
- `TestRequest` — core request; holds all Test INFO fields + status + TR# (auto-generated as `TR-YYYY-XXXXX`)
- `PartGroup` — up to 10 per request (letters A–J), holds all Part INFO fields
- `Comment` — threaded comments on each request, visible to both sides

**Status flow:**
```
submitted → in_progress (engineer accepts)  → closed (engineer uploads result file)
submitted → returned   (engineer sends back) → submitted (client resubmits)
```

**Database:** SQLite at `instance/app.db`. Seeded via `seed_db()` in `run.py`.

**File uploads:** Engineer-uploaded result files stored in `uploads/` and served via `engineer.download_result`. Closed requests allow client download for 90 days (`can_be_downloaded` property on `TestRequest`).

## Key conventions

- CSRF protection via Flask-WTF on all POST forms; templates must include `{{ csrf_token() }}` in a hidden field.
- Engineer visibility is scoped: engineers only see requests where `request.service_id` is in their assigned `services`.
- The only active test type is **Checkvalve Performance**. New test types can be added to `TestService` without code changes.
- Part group form fields use the naming convention `group_{LETTER}_{field}` (e.g. `group_A_vl_part_number`).
- Tooltip instructions are stored inline as `data-bs-toggle="tooltip" title="..."` on form labels.

## Colours (Vernay brand)

- Teal: `#347A80` (primary)
- Orange: `#EB7704` (accent / returned status)
- White: `#FFFFFF`

Defined as CSS variables in `app/static/css/style.css`.
