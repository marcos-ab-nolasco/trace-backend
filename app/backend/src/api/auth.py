import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
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
from src.core.dependencies import get_current_user
from src.core.rate_limit import limiter
from src.core.security import create_access_token, hash_password, verify_password
from src.db.models.user import User
from src.db.session import get_db
from src.schemas.auth import Token
from src.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])

basic_auth_scheme = HTTPBasic()

logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        logger.warning(f"Registration failed: email={user_data.email} reason=already_exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"User registered: user_id={new_user.id} email={new_user.email}")

    return new_user


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
    result = await db.execute(select(User).where(User.email == credentials.username))
    user = result.scalar_one_or_none()

    # Verify user and password
    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning(f"Login failed: email={credentials.username} reason=invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Create tokens (sub must be string)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_session(str(user.id))

    set_refresh_cookie(response, refresh_token)

    logger.info(f"Login successful: user_id={user.id} email={user.email}")

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
        user_id = UUID(session["user_id"])
    except (ValueError, TypeError) as err:
        logger.warning("Token refresh failed: reason=invalid_session_user")
        await delete_session(refresh_cookie)
        clear_refresh_cookie(response)
        raise credentials_exception from err

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"Token refresh failed: reason=user_not_found user_id={user_id}")
        await delete_session(refresh_cookie)
        clear_refresh_cookie(response)
        raise credentials_exception

    # Rotate session cookie and mint new access token
    new_refresh_token = await replace_session(refresh_cookie, str(user.id))
    set_refresh_cookie(response, new_refresh_token)

    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Logout user by deleting refresh session and clearing cookie."""

    refresh_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if refresh_cookie:
        await delete_session(refresh_cookie)

    clear_refresh_cookie(response)

    logger.info("Logout successful: user_id=%s", current_user.id)

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current authenticated user information."""
    return current_user
