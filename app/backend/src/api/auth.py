import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.session import (
    clear_refresh_cookie,
    create_session,
    delete_session,
    get_session,
    replace_session,
    set_refresh_cookie,
)
from src.core.config import get_settings
from src.core.dependencies import get_current_architect
from src.core.rate_limit import limiter
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models.architect import Architect
from src.db.models.organization import Organization
from src.db.session import get_db
from src.schemas.architect import ArchitectCreate, ArchitectRead
from src.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["authentication"])

basic_auth_scheme = HTTPBasic()

logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/register", response_model=ArchitectRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    architect_data: ArchitectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Architect:
    """Register a new architect along with their organization."""
    # Check if architect already exists
    result = await db.execute(select(Architect).where(Architect.email == architect_data.email))
    existing_architect = result.scalar_one_or_none()

    if existing_architect:
        logger.warning(
            "Registration failed: email=%s reason=already_exists", architect_data.email
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    try:
        # Create organization first so we can assign architect to it
        organization = Organization(name=architect_data.organization_name)
        db.add(organization)
        await db.flush()

        # Create architect tied to the organization
        new_architect = Architect(
            organization_id=organization.id,
            email=architect_data.email,
            full_name=architect_data.full_name,
            phone=architect_data.phone,
            hashed_password=hash_password(architect_data.password),
            is_authorized=True,
        )

        db.add(new_architect)
        await db.commit()
        await db.refresh(new_architect)

        logger.info(
            "Architect registered: architect_id=%s email=%s organization_id=%s",
            new_architect.id,
            new_architect.email,
            organization.id,
        )

        return new_architect

    except IntegrityError as exc:
        await db.rollback()
        logger.warning(
            "Registration failed due to integrity error: email=%s org=%s error=%s",
            architect_data.email,
            architect_data.organization_name,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed due to conflicting data (email or organization name).",
        ) from exc


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials, Depends(basic_auth_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
) -> Token:
    """Login with email and password to get access and refresh tokens."""
    # Find user by email
    result = await db.execute(select(Architect).where(Architect.email == credentials.username))
    architect = result.scalar_one_or_none()

    # Verify architect and password
    if not architect or not verify_password(credentials.password, architect.hashed_password):
        logger.warning("Login failed: email=%s reason=invalid_credentials", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Create tokens (sub must be string)
    access_token = create_access_token(data={"sub": str(architect.id)})
    refresh_token = await create_session(str(architect.id))

    set_refresh_cookie(response, refresh_token)

    logger.info("Login successful: architect_id=%s email=%s", architect.id, architect.email)

    return Token(access_token=access_token)


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Refresh access token using refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    refresh_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if refresh_cookie is None:
        logger.warning("Token refresh failed: reason=missing_cookie")
        raise credentials_exception

    session = await get_session(refresh_cookie)
    if session is None:
        logger.warning("Token refresh failed: reason=invalid_session")
        clear_refresh_cookie(response)
        raise credentials_exception

    try:
        architect_id = UUID(session["architect_id"])
    except (ValueError, TypeError) as err:
        logger.warning("Token refresh failed: reason=invalid_session_user")
        await delete_session(refresh_cookie)
        clear_refresh_cookie(response)
        raise credentials_exception from err

    # Verify architect exists
    result = await db.execute(select(Architect).where(Architect.id == architect_id))
    architect = result.scalar_one_or_none()

    if architect is None:
        logger.warning("Token refresh failed: reason=architect_not_found architect_id=%s", architect_id)
        await delete_session(refresh_cookie)
        clear_refresh_cookie(response)
        raise credentials_exception

    # Rotate session cookie and mint new access token
    new_refresh_token = await replace_session(refresh_cookie, str(architect.id))
    set_refresh_cookie(response, new_refresh_token)

    access_token = create_access_token(data={"sub": str(architect.id)})

    return Token(access_token=access_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_architect: Annotated[Architect, Depends(get_current_architect)],
) -> dict[str, str]:
    """Logout architect by deleting refresh session and clearing cookie."""

    refresh_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if refresh_cookie:
        await delete_session(refresh_cookie)

    clear_refresh_cookie(response)

    logger.info("Logout successful: architect_id=%s", current_architect.id)

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=ArchitectRead)
async def get_current_architect_info(
    current_architect: Annotated[Architect, Depends(get_current_architect)],
) -> Architect:
    """Get current authenticated architect information."""
    return current_architect
