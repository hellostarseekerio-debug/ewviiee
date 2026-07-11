# Installation Guide

## Prerequisites

- Python 3.12+
- (Optional) Tesseract OCR binary installed system-wide, if you want the
  OCR fallback engine to work: `apt install tesseract-ocr` (Linux),
  `brew install tesseract` (macOS), or the [Windows installer](https://github.com/UB-Mannheim/tesseract/wiki).
- (Optional) PostgreSQL server, if not using the default SQLite backend.

## 1. Get the code and install dependencies

```bash
git clone <this repository>
cd ewviiee
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set, at minimum:

- `OAP_SECRET_KEY` - generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `OAP_ENCRYPTION_KEY` - generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `OAP_ENVIRONMENT=production` when deploying for real use (this activates
  the startup safety checks in `Settings.assert_secure_for_production`)
- `OAP_CORS_ALLOWED_ORIGINS` - the exact origin(s) the GUI/any browser
  client will call the API from (never `*` in production)

Leave `OAP_AI_PROVIDER=local` unless your office has decided to use a
specific AI provider - see `docs/PRIVACY.md` before changing this.

## 3. Initialize the database

```bash
alembic upgrade head
```

## 4. Create the first administrator account

Do this directly against the database (never over the network):

```bash
python scripts/create_admin.py --username admin --full-name "Jane Doe"
```

You'll be prompted for a password meeting the office password policy
(12+ characters, upper/lower/digit/special character).

## 5. Generate sample data (optional, for a test run)

```bash
python scripts/generate_sample_data.py
```

## 6. Run

**API backend:**

```bash
python -m app.api.main
```

Visit `http://127.0.0.1:8000/docs` for the interactive API documentation.

**Desktop GUI:**

```bash
python -m app.gui.main
```

Sign in with the administrator account created in step 4.

## 7. Set up scheduled backups

Add a cron job (Linux/macOS) or Scheduled Task (Windows) to run:

```bash
python scripts/backup_db.py
```

daily. See `docs/admin_guide.md` for restore instructions.

## Building a standalone installer

See `scripts/build_windows.py` and `scripts/build_macos.py`
(PyInstaller-based). These must be run on the target OS - PyInstaller does
not cross-compile. Run with `--smoke-test` first to verify PyInstaller and
the GUI entrypoint are ready before attempting a full build:

```bash
python scripts/build_windows.py --smoke-test   # or build_macos.py
python scripts/build_windows.py                # full build
```

Output: `dist/OfficeAutomationPlatform/OfficeAutomationPlatform.exe`
(Windows) or `dist/OfficeAutomationPlatform.app` (macOS, unsigned - see
the script's docstring for code-signing/notarization notes).

## Troubleshooting

See `docs/TROUBLESHOOTING.md`.
