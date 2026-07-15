# Auth Service

## Setup

```bash
cp .env.example .env   # configure DATABASE_URL, SECRET_KEY, EMAIL_USER, EMAIL_PASSWORD
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload
```

## Endpoints

Base: `/api/v1/auth`

### `POST /register`

Register a new user.

```json
// Request
{ "email": "user@example.com", "password": "Str0ng!Pass" }
// Response 201
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### `POST /login`

```json
// Request
{ "email": "user@example.com", "password": "Str0ng!Pass" }
// Response 200
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### `POST /refresh`

```json
// Request
{ "refresh_token": "..." }
// Response 200
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### `POST /forgot-password`

Sends a password reset email with a one-time token (1hr expiry).

```json
// Request
{ "email": "user@example.com" }
// Response 200
{ "message": "If that email is registered, you will receive a password reset link" }
```

### `POST /reset-password`

```json
// Request
{ "token": "...", "password": "NewStr0ng!Pass" }
// Response 200
{ "message": "Password has been reset successfully" }
```

### `GET /api/v1/users/me`

Requires `Authorization: Bearer <access_token>` header.

```json
// Response 200
{ "id": "uuid", "email": "user@example.com", "is_active": true }
```

### `GET /health`

```json
// Response 200
{ "status": "ok" }
```

## Run Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
