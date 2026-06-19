"""Authentication router - login, register, token management, RBAC."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Role hierarchy and permissions (mirrors role_permissions table)
ROLE_PERMISSIONS = {
    "admin": {"view_somatic", "view_psychiatric", "view_private", "upload", "annotate",
              "admin", "export", "print", "ai_query", "manage_users", "change_own_password"},
    "super_editor": {"view_somatic", "view_psychiatric", "view_private", "upload", "annotate",
                     "export", "print", "ai_query", "change_own_password"},
    "editor": {"view_somatic", "view_psychiatric", "upload", "annotate",
               "export", "print", "ai_query", "change_own_password"},
    "viewer": {"view_somatic", "view_psychiatric", "print"},
}


# Pydantic schemas
class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: Optional[str] = None
    role: str = "viewer"

class UserResponse(BaseModel):
    id: str
    username: str
    full_name: str
    email: Optional[str]
    role: str
    is_active: bool
    is_system_admin: bool = False
    permissions: list[str] = []

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt directly (passlib incompatible with newer bcrypt); 72-byte limit handled
    return bcrypt.checkpw(plain_password.encode()[:72], hashed_password.encode())

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def user_permissions(role: str) -> set:
    return ROLE_PERMISSIONS.get(role, set())


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ugyldig autentisering",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_permission(permission: str):
    """Dependency that checks if user's role grants a permission."""
    async def checker(current_user: User = Depends(get_current_user)):
        if permission not in user_permissions(current_user.role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ikke tilstrekkelig tilgang")
        return current_user
    return checker


def require_role(*roles):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ikke tilstrekkelig tilgang")
        return current_user
    return role_checker


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_system_admin=bool(user.is_system_admin),
        permissions=sorted(user_permissions(user.role)),
    )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Feil brukernavn eller passord",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return Token(access_token=access_token, token_type="bearer", user=_user_response(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any logged-in user can change their own password.
    EXCEPTION: the system admin (created at install) cannot change password via web -
    it must be changed via the terminal command 'endre-admin-passord'.
    """
    if current_user.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System-admin passord kan kun endres via terminal (kommando: endre-admin-passord)",
        )
    if "change_own_password" not in user_permissions(current_user.role):
        raise HTTPException(status_code=403, detail="Din rolle kan ikke endre passord")
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Feil nåværende passord")

    current_user.password_hash = get_password_hash(data.new_password)
    current_user.must_change_password = False
    await db.commit()
    return {"message": "Passord endret"}
