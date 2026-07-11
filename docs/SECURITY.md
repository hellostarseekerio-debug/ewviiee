# Security Guide

This document describes the security controls implemented in the Office
Automation Platform and the operational practices required to keep them
effective. It is written for the office's IT administrator.

## Authentication

- Passwords are hashed with bcrypt (via `passlib`), never stored or logged
  in plaintext.
- Password policy (enforced on every account creation): minimum 12
  characters, at least one uppercase letter, one lowercase letter, one
  digit, and one special character (`app/core/security.py::validate_password_policy`).
- Accounts lock for 15 minutes after 5 consecutive failed login attempts
  (`MAX_FAILED_LOGIN_ATTEMPTS` / `LOCKOUT_DURATION_MINUTES`), and a
  successful login resets the counter.
- Access tokens (JWT, HS256) expire after 60 minutes by default
  (`OAP_ACCESS_TOKEN_EXPIRE_MINUTES`).
- The login endpoint (`POST /api/auth/token`) is rate-limited
  (`OAP_RATE_LIMIT_LOGIN`, default `5/minute` per client IP) as defense in
  depth against brute-force attempts, in addition to account lockout.
- There is deliberately **no open user-registration endpoint**. The very
  first account in an empty database can self-register via
  `POST /api/auth/users` (and is always forced to the `admin` role
  regardless of what role was requested) - every account after that must be
  created by an authenticated admin via `POST /api/auth/admin/users`, or
  via `scripts/create_admin.py` run directly on the server (recommended,
  since it never touches the network).

## Authorization (RBAC)

Four roles, lowest to highest privilege: `viewer` < `reviewer` < `editor` <
`admin`. Enforced server-side on every relevant endpoint via
`app.api.deps.require_role` - there is no client-side-only permission
check anywhere.

| Action | Minimum role |
|---|---|
| View/search documents | viewer |
| Approve/reject a document | reviewer |
| Upload files, run workflows, roll back a version | editor |
| Create/manage users, change system settings (incl. the cloud-AI switch), delete (soft) a document | admin |

The same role checks are enforced in the desktop GUI (buttons are disabled,
not merely hidden, for under-privileged roles) since the GUI talks to the
same database as a trusted peer of the API, not through it.

## File upload / import safety

Every uploaded or imported file passes through `app/core/file_safety.py`
before it is processed:

1. **Extension allowlist** (`OAP_ALLOWED_UPLOAD_EXTENSIONS`) - anything not
   on the list is rejected; a fixed set of executable/script extensions
   (`.exe`, `.dll`, `.bat`, `.sh`, `.js`, ...) is always blocked even if
   misconfigured into the allowlist.
2. **Size limit** (`OAP_MAX_UPLOAD_SIZE_BYTES`, default 25 MB).
3. **Magic-byte signature check** - the file's actual header bytes must
   match its claimed extension (catches a renamed executable disguised as
   a `.pdf`).
4. **Filename handling** - the client-supplied filename is never used to
   build a server-side path. It is sanitized (rejecting any path
   separator or `..` sequence) for display purposes only; the file is
   always stored under a freshly generated random name.
5. **Path traversal guard** (`app.core.file_safety.resolve_within_root`) -
   any endpoint that accepts a path string from a client (notably
   `/api/workflows/run`'s `document_paths`) resolves and verifies it falls
   under an approved root (`local_import_root`, `archive_root`,
   `export_root`, or a configured Dropbox/Google Drive/OneDrive root)
   before the file is ever opened. A path outside every root is rejected
   per-document with a clear reason - it never crashes the request or
   silently narrows to a "safe" path.

## API security

- **CORS**: `allow_origins` must be an explicit list (`OAP_CORS_ALLOWED_ORIGINS`);
  `"*"` combined with credentials is rejected outright in production
  (`Settings.assert_secure_for_production`).
- **Security headers** on every response: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'`,
  `Referrer-Policy: no-referrer`, `Permissions-Policy` disabling
  camera/microphone/geolocation, and HSTS.
- **Rate limiting** (`slowapi`) on the login endpoint and on
  upload/workflow-run endpoints (`OAP_RATE_LIMIT_DEFAULT`, default
  `120/minute`).
- **Global exception handler**: unhandled exceptions are logged in full
  server-side but only ever return a generic `"An internal error
  occurred"` message to the client - stack traces, file paths and query
  text never reach the network.
- **Input validation**: every request body is a Pydantic model with
  explicit constraints (e.g. `list_documents`'s `limit` is clamped to
  `[1, 200]` so a client cannot force an unbounded query).
- The API binds to `127.0.0.1` by default (`OAP_API_HOST`) - it must be
  explicitly reconfigured (and placed behind a reverse proxy/VPN) to be
  reachable from other machines.

## Secrets and encryption at rest

- `app.core.security.SecretBox` wraps `cryptography.Fernet` for any secret
  that needs to be stored in the database. It **fails closed**: if
  `OAP_ENCRYPTION_KEY` is not set, it raises
  `EncryptionKeyMissingError` rather than silently generating a throwaway
  key - a throwaway key would make previously-encrypted data permanently
  unreadable after the next restart, which is worse than refusing to run.
  Generate a key with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `Settings.assert_secure_for_production()` refuses to start when
  `OAP_ENVIRONMENT=production` and either `OAP_SECRET_KEY` is still the
  shipped default or `OAP_ENCRYPTION_KEY` is unset.
- AI provider API keys are read only from environment variables/`.env` on
  the server process; they are never sent to, stored in, or displayed by
  the desktop GUI or any HTTP response.

## Audit trail

Every authentication event, permission denial, file upload/rejection,
workflow run, approval/rejection, rollback, soft-deletion, and system
setting change is written to the `audit_logs` table
(`app.core.logging_config.record_audit`) with actor, action, resource, and
outcome. This table is intentionally append-only from the application's
perspective - there is no API endpoint that modifies or deletes an audit
log row.

## Known limitations / recommended hardening for a real deployment

- TLS termination is expected to be handled by a reverse proxy (nginx,
  Caddy, IIS ARR) in front of `uvicorn` - the API itself serves plain HTTP.
- The in-memory rate limiter (`slowapi`'s default backend) resets on
  process restart and does not share state across multiple API worker
  processes; for a multi-worker production deployment, back it with Redis
  (`slowapi` supports this via its `storage_uri` option).
- There is no built-in 2FA/MFA. If required by office policy, put the API
  behind an SSO/reverse-proxy layer that provides it.
- Run `scripts/backup_db.py` on a schedule (see `docs/admin_guide.md`) and
  store backups somewhere the application server cannot itself reach, so a
  compromise of the server doesn't also compromise the backups.
