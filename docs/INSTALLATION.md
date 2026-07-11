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

Both platforms follow the same two steps: PyInstaller bundles the app,
then a platform-native packager wraps that into the artifact you actually
hand to office staff. These must run on the target OS - PyInstaller does
not cross-compile.

### Windows: .exe installer

```bash
python scripts/build_windows.py --smoke-test   # verify PyInstaller + entrypoint first
python scripts/build_windows.py                # full build -> dist/OfficeAutomationPlatform/
```

This bundles `config/`, `alembic/`, and `alembic.ini` alongside the
executable, and embeds version metadata from
`packaging/windows/version_info.txt`. To produce a proper installer with a
Start Menu shortcut and uninstaller:

```bash
# Install Inno Setup first: https://jrsoftware.org/isinfo.php
iscc packaging\windows\installer.iss
```

Output: `dist/installer/OfficeAutomationPlatform-Setup-0.1.0.exe`. The
installer deliberately does **not** auto-create a database or admin
account - staff must still follow this guide's steps 3-4 after installing.

Optional: drop your office's icon at `packaging/windows/icon.ico` before
building for a branded result (none is shipped - see that path's
referencing comment in `build_windows.py`).

### macOS: .app / .dmg

```bash
python scripts/build_macos.py --smoke-test     # verify PyInstaller + entrypoint first
python scripts/build_macos.py                  # full build -> dist/OfficeAutomationPlatform.app
bash packaging/macos/create_dmg.sh             # wrap into dist/OfficeAutomationPlatform-0.1.0.dmg
```

The `.app`/`.dmg` are **unsigned** by default - macOS Gatekeeper will block
them on any machine other than the one that built them. For real
distribution, you need an Apple Developer ID certificate; see the
`codesign`/`xcrun notarytool`/`xcrun stapler` commands documented in
`packaging/macos/create_dmg.sh`'s header comment.

Optional: drop your office's icon at `packaging/macos/icon.icns` before
building for a branded result (none is shipped).

### What ships in the installer vs. what doesn't

Included: the application, `config/` (rule YAML), `alembic/` (migrations),
`.env.example`, and key docs. **Not** included, by design: any `.env` file,
database file, encryption/secret keys, or user accounts - every
installation starts from the same clean slate described in this guide,
never with default credentials baked in.

## Troubleshooting

See `docs/TROUBLESHOOTING.md`.
