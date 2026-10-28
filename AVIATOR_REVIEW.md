# Aviator router review

## Changes made to `app/routers/aviator.py`

- Converted the module from creating its own `FastAPI` application to exporting an `APIRouter`, matching `app/main.py` (`app.include_router(aviator.router, prefix="/api/v1/aviator", ...)`).
- Kept `startup_initialize_super_admin()` as a callable function because `main.py` invokes it from the application startup hook.
- Removed per-router CORS middleware; CORS belongs on the main application. The main application currently configures CORS twice and should be cleaned up separately.
- Updated the OAuth2 `tokenUrl` to `/api/v1/aviator/auth/login` to match the mounted API prefix.
- Added composite payment indexes for user/status/archive/review and status/archive/created-date query patterns. Explicit index creation supports existing databases as well as fresh databases.
- Removed the asynchronous declaration from `/payments/submit`, because its SQLAlchemy session and file operations are synchronous; FastAPI can run a normal `def` endpoint in its thread pool.
- Added a 5 MB limit for payment-proof uploads and cleanup of partial files if upload or database persistence fails.
- Reduced N+1 queries in admin payment listings and referral dashboard calculations.
- Added Pydantic field length constraints for signup, login, staff, and payment-option payloads.

## Static checks

- Python syntax compilation passed for the modified router.
- AST inspection found 20 route registrations, no duplicate function names, no duplicate route handler names, and no duplicate HTTP-method/path pairs.
- Full import/startup and generated OpenAPI checks could not be run in this environment because the installed Python environment is missing the `python-jose` dependency. Install the project's `requirements.txt` and run the app/tests locally to complete runtime validation.

## Important findings / remaining work

- This file uses synchronous SQLAlchemy (`Session`, `create_engine`), not MongoDB/Motor. The MongoDB/Motor code lives elsewhere in the project; changing this router to Motor would be a separate migration, not an optimization.
- There is no OCR scanning or external real-time crash-game feed logic in this router. `/admin/matches` is a placeholder, and `/predictor/demo` generates a random standalone multiplier. It does not predict or retrieve a real Aviator game outcome.
- `transaction_ref` is indexed but not unique, so concurrent duplicate payment submissions can still be stored. Before adding a unique constraint, check and reconcile existing duplicates, then add a database-level unique constraint and handle integrity errors.
- `JWT_SECRET` still has a development fallback for compatibility. Configure a strong secret in the production environment; do not deploy using the fallback.
- Payment recipient details are seeded as defaults in code. Production payment details should be configured through the Super Admin interface and should not be treated as secrets embedded in source.
- The main application (`app/main.py`) still registers the NexusBet router twice and adds CORS middleware twice. This patch intentionally changes only the Aviator router; verify frontend paths before changing those mounts.
- Existing SQLite databases are not backed up or included in this patch bundle. Back up your database and uploads before deploying code changes.
