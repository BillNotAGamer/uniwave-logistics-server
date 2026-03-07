# FastAPI Migration Skeleton

## Requirements
- Python 3.11+
- PostgreSQL (recommended for local parity with production)

## Local setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. Copy env values:
   ```bash
   cp .env.example .env
   ```
4. Run migrations manually:
   ```bash
   alembic upgrade head
   ```
5. Seed roles and optional admin user:
   ```bash
   app-seed
   ```
6. Start the API:
   ```bash
   uvicorn main:app --reload
   ```

## Seeding
- Always seeds default roles: `Admin`, `ContentEditor`, `User`.
- Optionally seeds admin user when both env vars are set:
  - `SEED_ADMIN_EMAIL`
  - `SEED_ADMIN_PASSWORD`
- Optional display and verification flags:
  - `SEED_ADMIN_DISPLAY_NAME` (default `Admin`)
  - `SEED_ADMIN_MARK_EMAIL_VERIFIED` (default `true`)
- Seed roles only:
  ```bash
  app-seed --skip-admin
  ```

## Migration and startup policy
- The API does not run Alembic migrations automatically on startup.
- In development, optional startup DB check is enabled by default:
  - `ENABLE_DEV_STARTUP_DB_CHECK=true`
  - `DEV_STARTUP_REQUIRE_ALEMBIC_VERSION=true`
- If the dev check fails with missing `alembic_version`, run:
  ```bash
  alembic upgrade head
  ```

## Docs behavior by environment
- `ENVIRONMENT=production`: OpenAPI and Swagger/ReDoc are disabled.
- Non-production environments: docs are available at `/docs`, `/redoc`, `/openapi.json`.

## Testing
- Run smoke tests:
  ```bash
  pytest -q
  ```

## Deployment guide (Render + Neon + Cloudinary)

### Neon
- Create a Neon Postgres database.
- Set `DATABASE_URL` with async driver format:
  - `postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME?sslmode=require`

### Render
1. Create a Web Service for this repo.
2. Build command:
   ```bash
   pip install -e .
   ```
3. Start command:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. Use a pre-deploy step (or manual one-time ops) for migrations and seed:
   ```bash
   alembic upgrade head && app-seed
   ```

### Required env vars (production baseline)
- `ENVIRONMENT=production`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `CORS_ALLOWED_ORIGINS`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`

### Cloudinary env vars
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `CLOUDINARY_FOLDER` (optional, default `blog-thumbnails`)
