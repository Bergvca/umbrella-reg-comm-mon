# UI Layer — Phase 1 Detailed Implementation Plan

**Goal:** A runnable FastAPI backend with JWT authentication, RBAC, user/group admin CRUD, and tests. No frontend yet.

**Outcome:** `python -m umbrella_ui` starts a server on port 8000. A user can log in with username + password, receive a JWT, and use that token to call protected endpoints for managing users, groups, and roles.

---

## Prerequisites

- PostgreSQL running with migrations V1–V6 applied (schemas: `iam`, `policy`, `alert`, `review`)
- Python 3.11+ with the project virtual environment active
- The `umbrella-connector-framework` package installed (for `setup_logging` and `umbrella_schema`)

---

## Step 1: Create `pyproject.toml`

**File:** `ui/backend/pyproject.toml`

```toml
[project]
name = "umbrella-ui-backend"
version = "0.1.0"
description = "Umbrella UI backend — FastAPI server for compliance review"
requires-python = ">=3.11"
dependencies = [
    "umbrella-connector-framework",
    "fastapi>=0.115",
    "uvicorn>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "httpx>=0.27",
]

[project.scripts]
umbrella-ui = "umbrella_ui.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["umbrella_ui"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

After creating the file, install in editable mode:

```bash
pip install -e ui/backend/
```

---

## Step 2: Create `umbrella_ui/__init__.py`

**File:** `ui/backend/umbrella_ui/__init__.py`

Empty file. Just needs to exist so Python treats it as a package.

```python
```

---

## Step 3: Create `config.py`

**File:** `ui/backend/umbrella_ui/config.py`

This file defines all settings. Follow the project convention of using pydantic-settings with an env prefix. The UI backend needs connection strings for each PG schema role, plus JWT config.

```python
"""UI backend configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level settings for the UI backend.

    All env vars are prefixed with ``UMBRELLA_UI_``.
    Example: ``UMBRELLA_UI_JWT_SECRET=mysecret``
    """

    model_config = SettingsConfigDict(env_prefix="UMBRELLA_UI_")

    # --- Database -----------------------------------------------------------
    # Four separate connection strings, one per PG role.
    # Format: postgresql+asyncpg://iam_rw:password@host:5432/umbrella
    iam_database_url: str = Field(
        description="Async SQLAlchemy URL for the iam_rw role",
    )
    policy_database_url: str = Field(
        description="Async SQLAlchemy URL for the policy_rw role",
    )
    alert_database_url: str = Field(
        description="Async SQLAlchemy URL for the alert_rw role",
    )
    review_database_url: str = Field(
        description="Async SQLAlchemy URL for the review_rw role",
    )

    # --- JWT ----------------------------------------------------------------
    jwt_secret: str = Field(
        description="Secret key used to sign JWT tokens",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="Access token lifetime in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token lifetime in days",
    )

    # --- Server -------------------------------------------------------------
    host: str = Field(default="0.0.0.0", description="Bind address")
    port: int = Field(default=8000, description="Bind port")
    log_level: str = Field(default="INFO", description="Log level")
    log_json: bool = Field(
        default=True,
        description="Use JSON log output (True for prod, False for dev)",
    )
```

**Env vars needed to run (example `.env` for local dev):**

```
UMBRELLA_UI_IAM_DATABASE_URL=postgresql+asyncpg://iam_rw:password@localhost:5432/umbrella
UMBRELLA_UI_POLICY_DATABASE_URL=postgresql+asyncpg://policy_rw:password@localhost:5432/umbrella
UMBRELLA_UI_ALERT_DATABASE_URL=postgresql+asyncpg://alert_rw:password@localhost:5432/umbrella
UMBRELLA_UI_REVIEW_DATABASE_URL=postgresql+asyncpg://review_rw:password@localhost:5432/umbrella
UMBRELLA_UI_JWT_SECRET=dev-secret-change-me
```

---

## Step 4: Create `db/engine.py`

**File:** `ui/backend/umbrella_ui/db/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/db/engine.py`

Creates four async SQLAlchemy engines and session factories, one per PG role.

```python
"""Async SQLAlchemy engines — one per database role."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from umbrella_ui.config import Settings


def _make_engine(url: str):
    return create_async_engine(url, echo=False, pool_size=5, max_overflow=10)


def _make_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class DatabaseEngines:
    """Holds all four engines and their session factories.

    Created once at startup and stored on ``app.state``.
    """

    def __init__(self, settings: Settings) -> None:
        self.iam_engine = _make_engine(settings.iam_database_url)
        self.policy_engine = _make_engine(settings.policy_database_url)
        self.alert_engine = _make_engine(settings.alert_database_url)
        self.review_engine = _make_engine(settings.review_database_url)

        self.iam_session = _make_session_factory(self.iam_engine)
        self.policy_session = _make_session_factory(self.policy_engine)
        self.alert_session = _make_session_factory(self.alert_engine)
        self.review_session = _make_session_factory(self.review_engine)

    async def close(self) -> None:
        await self.iam_engine.dispose()
        await self.policy_engine.dispose()
        await self.alert_engine.dispose()
        await self.review_engine.dispose()
```

---

## Step 5: Create SQLAlchemy ORM Models for `iam` schema

**File:** `ui/backend/umbrella_ui/db/models/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/db/models/iam.py`

These models MUST exactly mirror the tables from `infrastructure/postgresql/migrations/V2__iam.sql`. Column names, types, and constraints must match. Do NOT let SQLAlchemy create/alter tables — we use Flyway migrations for that.

```python
"""SQLAlchemy ORM models for the iam schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "iam"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    user_groups: Mapped[list[UserGroup]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "iam"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = {"schema": "iam"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    user_groups: Mapped[list[UserGroup]] = relationship(back_populates="group")
    group_roles: Mapped[list[GroupRole]] = relationship(back_populates="group")


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = {"schema": "iam"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    user: Mapped[User] = relationship(back_populates="user_groups", foreign_keys=[user_id])
    group: Mapped[Group] = relationship(back_populates="user_groups")


class GroupRole(Base):
    __tablename__ = "group_roles"
    __table_args__ = {"schema": "iam"}

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iam.users.id"),
    )
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    group: Mapped[Group] = relationship(back_populates="group_roles")
    role: Mapped[Role] = relationship()
```

**Key rules:**
- Every `__table_args__` must include `{"schema": "iam"}` — the tables live in the `iam` schema, not `public`.
- Use `UUID(as_uuid=True)` for uuid columns.
- Use `server_default=text(...)` for defaults — these are database-side defaults, not Python-side.
- `password_hash` is a plain `Text` column; the bcrypt hash is generated in the auth layer.

---

## Step 6: Create Auth Modules

### 6a: Password Hashing

**File:** `ui/backend/umbrella_ui/auth/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/auth/password.py`

```python
"""Bcrypt password hashing and verification."""

from __future__ import annotations

from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _ctx.verify(plain, hashed)
```

### 6b: JWT Token Handling

**File:** `ui/backend/umbrella_ui/auth/jwt.py`

```python
"""JWT token creation and validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from umbrella_ui.config import Settings


def create_access_token(
    user_id: UUID,
    roles: list[str],
    settings: Settings,
) -> str:
    """Create a signed JWT access token.

    Payload::

        {
            "sub": "<user-uuid>",
            "roles": ["reviewer", "supervisor"],
            "exp": <unix-timestamp>
        }
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes,
    )
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: UUID,
    settings: Settings,
) -> str:
    """Create a signed JWT refresh token (longer-lived, no roles)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days,
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> dict:
    """Decode and validate a JWT token. Raises ``JWTError`` on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
```

### 6c: Pydantic Schemas for Auth

**File:** `ui/backend/umbrella_ui/auth/schemas.py`

```python
"""Request/response schemas for authentication endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    """Returned by GET /auth/me."""

    id: UUID
    username: str
    email: str
    is_active: bool
    roles: list[str]
```

### 6d: RBAC Dependencies

**File:** `ui/backend/umbrella_ui/auth/rbac.py`

This is the core authorization mechanism. It provides FastAPI dependencies that:
1. Extract the JWT from the `Authorization: Bearer <token>` header.
2. Decode it and look up the user.
3. Optionally check that the user has one of the required roles.

```python
"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from umbrella_ui.auth.jwt import decode_token
from umbrella_ui.config import Settings
from umbrella_ui.db.models.iam import Group, GroupRole, Role, User, UserGroup

logger = structlog.get_logger()

_bearer_scheme = HTTPBearer()


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _get_iam_session(request: Request) -> AsyncSession:
    return request.app.state.db.iam_session()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(_get_settings)],
    request: Request,
) -> dict:
    """Decode JWT and return ``{"id": UUID, "username": str, "roles": [...]}``."""
    try:
        payload = decode_token(credentials.credentials, settings)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "id": UUID(payload["sub"]),
        "roles": payload.get("roles", []),
    }


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that checks the user has at least one of the given roles.

    Usage in a router::

        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint(): ...

    Or to get the user dict at the same time::

        @router.get("/supervisors")
        async def supervisor_endpoint(user: dict = Depends(require_role("supervisor", "admin"))): ...

    Role hierarchy:
        - ``admin`` implies ``supervisor`` and ``reviewer``
        - ``supervisor`` implies ``reviewer``
    """
    # Expand role hierarchy so checking for "reviewer" also passes for admin/supervisor.
    HIERARCHY = {
        "admin": {"admin", "supervisor", "reviewer"},
        "supervisor": {"supervisor", "reviewer"},
        "reviewer": {"reviewer"},
    }
    expanded = set()
    for role in allowed_roles:
        expanded.update(HIERARCHY.get(role, {role}))

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_roles = set(user.get("roles", []))
        if not user_roles & expanded:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
```

**Important — role hierarchy:** The seed data has three roles: `admin`, `supervisor`, `reviewer`. The hierarchy means:
- An `admin` can access everything that `supervisor` and `reviewer` can.
- A `supervisor` can access everything that `reviewer` can.
- `require_role("reviewer")` allows all three roles through.
- `require_role("admin")` only allows `admin`.

---

## Step 7: Create Pydantic Schemas for Users/Groups

**File:** `ui/backend/umbrella_ui/schemas/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/schemas/common.py`

```python
"""Shared response schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
```

**File:** `ui/backend/umbrella_ui/schemas/iam.py`

```python
"""Request/response schemas for IAM endpoints (users, groups, roles)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Roles -------------------------------------------------------------------

class RoleOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


# --- Users -------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    email: str
    password: str  # plaintext — will be hashed by the endpoint


class UserUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserWithRoles(UserOut):
    """User with their resolved roles (for detail views)."""
    roles: list[str]


# --- Groups ------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class GroupDetail(GroupOut):
    """Group with its roles and member count."""
    roles: list[str]
    member_count: int


# --- Membership & Assignment -------------------------------------------------

class AddUserToGroup(BaseModel):
    group_id: UUID


class AssignRoleToGroup(BaseModel):
    role_id: UUID
```

---

## Step 8: Create FastAPI Dependencies (`deps.py`)

**File:** `ui/backend/umbrella_ui/deps.py`

Provides session dependencies for routers. Each dependency yields an `AsyncSession` scoped to a single request.

```python
"""FastAPI dependency-injection helpers for database sessions."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_iam_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.iam_session() as session:
        yield session


async def get_policy_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.policy_session() as session:
        yield session


async def get_alert_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.alert_session() as session:
        yield session


async def get_review_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.db.review_session() as session:
        yield session
```

---

## Step 9: Create Routers

### 9a: Auth Router

**File:** `ui/backend/umbrella_ui/routers/__init__.py` — empty

**File:** `ui/backend/umbrella_ui/routers/auth.py`

Three endpoints:
1. `POST /api/v1/auth/login` — takes username + password, returns JWT pair.
2. `POST /api/v1/auth/refresh` — takes a refresh token, returns a new access token.
3. `GET /api/v1/auth/me` — returns the current user profile + roles.

```python
"""Authentication endpoints: login, refresh, me."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umbrella_ui.auth.jwt import create_access_token, create_refresh_token, decode_token
from umbrella_ui.auth.password import verify_password
from umbrella_ui.auth.rbac import get_current_user
from umbrella_ui.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserProfile
from umbrella_ui.config import Settings
from umbrella_ui.db.models.iam import GroupRole, Role, User, UserGroup
from umbrella_ui.deps import get_iam_session

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _resolve_roles(user_id: UUID, session: AsyncSession) -> list[str]:
    """Resolve a user's effective roles via: user → user_groups → group_roles → roles."""
    stmt = (
        select(Role.name)
        .join(GroupRole, GroupRole.role_id == Role.id)
        .join(UserGroup, UserGroup.group_id == GroupRole.group_id)
        .where(UserGroup.user_id == user_id)
        .distinct()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Authenticate with username + password, receive JWT tokens."""
    settings: Settings = request.app.state.settings

    # 1. Look up user
    stmt = select(User).where(User.username == body.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # 2. Resolve roles
    roles = await _resolve_roles(user.id, session)

    # 3. Issue tokens
    access_token = create_access_token(user.id, roles, settings)
    refresh_token = create_refresh_token(user.id, settings)

    logger.info("user_login", user_id=str(user.id), username=user.username, roles=roles)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Exchange a refresh token for a new access + refresh token pair."""
    settings: Settings = request.app.state.settings

    try:
        payload = decode_token(body.refresh_token, settings)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = UUID(payload["sub"])

    # Verify user still exists and is active
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    roles = await _resolve_roles(user_id, session)
    access_token = create_access_token(user_id, roles, settings)
    refresh_token = create_refresh_token(user_id, settings)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserProfile)
async def me(
    user: Annotated[dict, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_iam_session)],
):
    """Return the current user's profile and resolved roles."""
    stmt = select(User).where(User.id == user["id"])
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    roles = await _resolve_roles(db_user.id, session)

    return UserProfile(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        is_active=db_user.is_active,
        roles=roles,
    )
```

### 9b: Users Router

**File:** `ui/backend/umbrella_ui/routers/users.py`

CRUD for users + group membership management. All endpoints require `admin` role.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/users` | List users (paginated) |
| `POST` | `/api/v1/users` | Create user (hashes password) |
| `GET` | `/api/v1/users/{id}` | Get user detail with resolved roles |
| `PATCH` | `/api/v1/users/{id}` | Update email or is_active |
| `GET` | `/api/v1/users/{id}/groups` | List user's groups |
| `POST` | `/api/v1/users/{id}/groups` | Add user to group |
| `DELETE` | `/api/v1/users/{id}/groups/{group_id}` | Remove user from group |

Implementation details:

- `POST /users` — hash the password with `hash_password()` from `auth/password.py`, store in `password_hash`. Return `UserOut` (never expose the hash).
- `GET /users/{id}` — return `UserWithRoles`. Resolve roles via the same `_resolve_roles()` join used in the auth router. Extract this into a shared utility (e.g., `umbrella_ui.auth.rbac._resolve_roles` or a dedicated function in the iam router).
- `PATCH /users/{id}` — only update fields present in the request body (partial update). Set `updated_at` to `now()`.
- `POST /users/{id}/groups` — insert into `iam.user_groups`. Set `assigned_by` to the current user's ID.
- `DELETE /users/{id}/groups/{group_id}` — delete from `iam.user_groups`.
- All endpoints use `Depends(require_role("admin"))`.
- Pagination: accept `offset` (default 0) and `limit` (default 50) query params. Return `PaginatedResponse[UserOut]`.

### 9c: Groups Router

**File:** `ui/backend/umbrella_ui/routers/groups.py`

CRUD for groups + role/policy assignment. All endpoints require `admin` role.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/groups` | List groups with role names and member count |
| `POST` | `/api/v1/groups` | Create group |
| `GET` | `/api/v1/groups/{id}` | Get group detail (roles + member count) |
| `PATCH` | `/api/v1/groups/{id}` | Update group name/description |
| `GET` | `/api/v1/groups/{id}/members` | List users in this group |
| `POST` | `/api/v1/groups/{id}/roles` | Assign a role to the group |
| `DELETE` | `/api/v1/groups/{id}/roles/{role_id}` | Remove a role from the group |

Implementation details:

- `GET /groups` — for each group, count members (`SELECT count(*) FROM iam.user_groups WHERE group_id = ...`) and list role names. Return `PaginatedResponse[GroupDetail]`.
- `POST /groups/{id}/roles` — insert into `iam.group_roles`. Set `assigned_by` to current user.
- `DELETE /groups/{id}/roles/{role_id}` — delete from `iam.group_roles`.

### 9d: Roles Router

**File:** `ui/backend/umbrella_ui/routers/roles.py`

Read-only — roles are seeded by migration V6 and not user-creatable.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/roles` | List all roles |

---

## Step 10: Create the FastAPI App Factory

**File:** `ui/backend/umbrella_ui/app.py`

```python
"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from umbrella_ui.config import Settings
from umbrella_ui.db.engine import DatabaseEngines

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB engines. Shutdown: dispose engines."""
    settings: Settings = app.state.settings
    db = DatabaseEngines(settings)
    app.state.db = db
    logger.info("database_engines_created")
    yield
    await db.close()
    logger.info("database_engines_closed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    Parameters
    ----------
    settings:
        If ``None``, settings are loaded from environment variables.
    """
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]

    app = FastAPI(
        title="Umbrella UI Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Register routers
    from umbrella_ui.routers.auth import router as auth_router
    from umbrella_ui.routers.users import router as users_router
    from umbrella_ui.routers.groups import router as groups_router
    from umbrella_ui.routers.roles import router as roles_router

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(groups_router)
    app.include_router(roles_router)

    # Health check (no auth required)
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "umbrella-ui-backend"}

    return app
```

---

## Step 11: Create the Entry Point

**File:** `ui/backend/umbrella_ui/__main__.py`

Follow the same pattern as `ingestion-api/umbrella_ingestion/__main__.py`:

```python
"""Entry point: ``python -m umbrella_ui``."""

from __future__ import annotations

import uvicorn

from umbrella_connector import setup_logging

from .config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    setup_logging(json=settings.log_json, level=settings.log_level)

    uvicorn.run(
        "umbrella_ui.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
```

---

## Step 12: Create Tests

### 12a: Test fixtures

**File:** `ui/backend/tests/__init__.py` — empty

**File:** `ui/backend/tests/conftest.py`

```python
"""Shared test fixtures for the UI backend."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from umbrella_ui.app import create_app
from umbrella_ui.auth.jwt import create_access_token
from umbrella_ui.auth.password import hash_password
from umbrella_ui.config import Settings
from umbrella_ui.db.models.iam import Base


def _test_settings(**overrides) -> Settings:
    """Create Settings with test defaults. Override any field via kwargs."""
    defaults = {
        "iam_database_url": "sqlite+aiosqlite://",
        "policy_database_url": "sqlite+aiosqlite://",
        "alert_database_url": "sqlite+aiosqlite://",
        "review_database_url": "sqlite+aiosqlite://",
        "jwt_secret": "test-secret",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def settings():
    return _test_settings()


@pytest.fixture
async def app(settings):
    """Create the FastAPI app with an in-memory SQLite DB for iam tables.

    NOTE: For Phase 1 tests, we only need the iam schema.
    SQLite doesn't support schemas, so tests use a single DB with unqualified table names.
    For proper integration tests with PG schemas, use a real PG database via testcontainers
    or a test PG instance. Phase 1 unit tests mock the DB session instead.
    """
    application = create_app(settings)
    return application


@pytest.fixture
async def client(app):
    """Async HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def make_admin_headers(settings: Settings, user_id: uuid.UUID | None = None) -> dict:
    """Create Authorization headers with an admin JWT for testing."""
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["admin"], settings)
    return {"Authorization": f"Bearer {token}"}


def make_reviewer_headers(settings: Settings, user_id: uuid.UUID | None = None) -> dict:
    """Create Authorization headers with a reviewer JWT for testing."""
    uid = user_id or uuid.uuid4()
    token = create_access_token(uid, ["reviewer"], settings)
    return {"Authorization": f"Bearer {token}"}
```

### 12b: Auth tests

**File:** `ui/backend/tests/test_auth.py`

Test the following scenarios. Each test should mock the DB session (or use a real PG if available) and call the endpoint via `client`.

| Test | What it verifies |
|---|---|
| `test_login_success` | Valid credentials → 200, returns `access_token` and `refresh_token` |
| `test_login_wrong_password` | Wrong password → 401 |
| `test_login_unknown_user` | Non-existent username → 401 |
| `test_login_inactive_user` | `is_active=False` → 403 |
| `test_me_valid_token` | Valid JWT → 200, returns user profile with roles |
| `test_me_no_token` | No Authorization header → 401/403 |
| `test_me_expired_token` | Expired JWT → 401 |
| `test_refresh_success` | Valid refresh token → 200, new token pair |
| `test_refresh_with_access_token` | Using an access token as refresh → 401 (wrong type) |

**Testing approach:** Since the DB session depends on a real PG with schemas, tests should either:
1. **Mock the session** — patch `get_iam_session` to return a mock `AsyncSession` with pre-configured query results. This is simpler and sufficient for unit tests.
2. **Use testcontainers** — spin up a real PG container, run migrations, test end-to-end. Better for integration tests but slower.

For Phase 1, prefer approach 1 (mocking) with a few integration tests if PG is available.

### 12c: RBAC tests

**File:** `ui/backend/tests/test_rbac.py`

| Test | What it verifies |
|---|---|
| `test_admin_can_access_admin_endpoint` | JWT with `roles: ["admin"]` → 200 |
| `test_reviewer_cannot_access_admin_endpoint` | JWT with `roles: ["reviewer"]` → 403 |
| `test_supervisor_can_access_reviewer_endpoint` | Role hierarchy: supervisor includes reviewer |
| `test_admin_can_access_reviewer_endpoint` | Role hierarchy: admin includes reviewer |
| `test_no_roles_gets_403` | JWT with `roles: []` → 403 |

### 12d: User/Group CRUD tests

**File:** `ui/backend/tests/test_users.py`

| Test | What it verifies |
|---|---|
| `test_create_user` | POST /users → 201, returns user without password_hash |
| `test_create_user_duplicate_username` | Duplicate username → 409 |
| `test_list_users` | GET /users → 200, returns paginated list |
| `test_get_user_detail` | GET /users/{id} → 200, includes resolved roles |
| `test_update_user` | PATCH /users/{id} → 200, updated fields returned |
| `test_add_user_to_group` | POST /users/{id}/groups → 200 |
| `test_remove_user_from_group` | DELETE /users/{id}/groups/{gid} → 204 |
| `test_non_admin_cannot_create_user` | Reviewer JWT → 403 |

**File:** `ui/backend/tests/test_groups.py`

| Test | What it verifies |
|---|---|
| `test_create_group` | POST /groups → 201 |
| `test_list_groups` | GET /groups → 200, includes role names and member count |
| `test_assign_role_to_group` | POST /groups/{id}/roles → 200 |
| `test_remove_role_from_group` | DELETE /groups/{id}/roles/{rid} → 204 |
| `test_list_group_members` | GET /groups/{id}/members → 200 |

---

## Step 13: Verify Everything Works

### Run the tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx aiosqlite

# Run all tests
pytest ui/backend/tests/ -v
```

### Start the server locally

Requires a running PostgreSQL with migrations applied:

```bash
# Set environment variables (or use a .env file)
export UMBRELLA_UI_IAM_DATABASE_URL="postgresql+asyncpg://iam_rw:password@localhost:5432/umbrella"
export UMBRELLA_UI_POLICY_DATABASE_URL="postgresql+asyncpg://policy_rw:password@localhost:5432/umbrella"
export UMBRELLA_UI_ALERT_DATABASE_URL="postgresql+asyncpg://alert_rw:password@localhost:5432/umbrella"
export UMBRELLA_UI_REVIEW_DATABASE_URL="postgresql+asyncpg://review_rw:password@localhost:5432/umbrella"
export UMBRELLA_UI_JWT_SECRET="dev-secret-change-me"
export UMBRELLA_UI_LOG_JSON="false"

# Start the server
python -m umbrella_ui
```

### Smoke test

```bash
# 1. Check health
curl http://localhost:8000/health
# → {"status":"ok","service":"umbrella-ui-backend"}

# 2. View auto-generated API docs
# Open http://localhost:8000/docs in a browser

# 3. Create a test user (need to insert directly into PG for the first user)
psql -U iam_rw -d umbrella -c "
INSERT INTO iam.users (username, email, password_hash)
VALUES ('admin', 'admin@example.com',
        '\$2b\$12\$LJ3m4ys4Gz0aO0E.fGKPwOp0XkNmFJP6jKx3RHTL3.CtxW5r/BFWK');
-- (this hash = bcrypt of 'password')
"

# 4. Add admin to an admin group
psql -U iam_rw -d umbrella -c "
INSERT INTO iam.groups (name) VALUES ('admins');
INSERT INTO iam.user_groups (user_id, group_id)
SELECT u.id, g.id FROM iam.users u, iam.groups g
WHERE u.username = 'admin' AND g.name = 'admins';
INSERT INTO iam.group_roles (group_id, role_id)
SELECT g.id, r.id FROM iam.groups g, iam.roles r
WHERE g.name = 'admins' AND r.name = 'admin';
"

# 5. Log in
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
# → {"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer"}

# 6. Use the token
TOKEN="<paste access_token here>"
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
# → {"id": "...", "username": "admin", "email": "admin@example.com", "is_active": true, "roles": ["admin"]}

# 7. List roles
curl http://localhost:8000/api/v1/roles -H "Authorization: Bearer $TOKEN"
# → [{"id": "...", "name": "admin", ...}, {"id": "...", "name": "supervisor", ...}, ...]
```

---

## File Checklist

Every file that Phase 1 must produce:

| # | File | Type |
|---|---|---|
| 1 | `ui/backend/pyproject.toml` | config |
| 2 | `ui/backend/umbrella_ui/__init__.py` | empty |
| 3 | `ui/backend/umbrella_ui/__main__.py` | entry point |
| 4 | `ui/backend/umbrella_ui/app.py` | FastAPI factory |
| 5 | `ui/backend/umbrella_ui/config.py` | settings |
| 6 | `ui/backend/umbrella_ui/deps.py` | DI helpers |
| 7 | `ui/backend/umbrella_ui/db/__init__.py` | empty |
| 8 | `ui/backend/umbrella_ui/db/engine.py` | DB engines |
| 9 | `ui/backend/umbrella_ui/db/models/__init__.py` | empty |
| 10 | `ui/backend/umbrella_ui/db/models/iam.py` | ORM models |
| 11 | `ui/backend/umbrella_ui/auth/__init__.py` | empty |
| 12 | `ui/backend/umbrella_ui/auth/password.py` | bcrypt |
| 13 | `ui/backend/umbrella_ui/auth/jwt.py` | JWT |
| 14 | `ui/backend/umbrella_ui/auth/schemas.py` | auth schemas |
| 15 | `ui/backend/umbrella_ui/auth/rbac.py` | RBAC deps |
| 16 | `ui/backend/umbrella_ui/schemas/__init__.py` | empty |
| 17 | `ui/backend/umbrella_ui/schemas/common.py` | shared schemas |
| 18 | `ui/backend/umbrella_ui/schemas/iam.py` | IAM schemas |
| 19 | `ui/backend/umbrella_ui/routers/__init__.py` | empty |
| 20 | `ui/backend/umbrella_ui/routers/auth.py` | auth endpoints |
| 21 | `ui/backend/umbrella_ui/routers/users.py` | user CRUD |
| 22 | `ui/backend/umbrella_ui/routers/groups.py` | group CRUD |
| 23 | `ui/backend/umbrella_ui/routers/roles.py` | roles (read-only) |
| 24 | `ui/backend/tests/__init__.py` | empty |
| 25 | `ui/backend/tests/conftest.py` | fixtures |
| 26 | `ui/backend/tests/test_auth.py` | auth tests |
| 27 | `ui/backend/tests/test_rbac.py` | RBAC tests |
| 28 | `ui/backend/tests/test_users.py` | user tests |
| 29 | `ui/backend/tests/test_groups.py` | group tests |

---

## What Phase 1 Does NOT Include

- No Elasticsearch queries (Phase 2)
- No alert/message/queue/decision endpoints (Phase 2)
- No frontend (Phase 4)
- No Dockerfile or K8s manifests (Phase 7)
- No SSO/OIDC (future)
- No policy/rule CRUD (Phase 3)
