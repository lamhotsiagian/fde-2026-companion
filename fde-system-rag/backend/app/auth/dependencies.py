from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.config import settings
from app.db.main import SessionDep
from app.db.models import User, TenantUser
from app.users import service as user_service
from sqlalchemy import select
from uuid import UUID

from .schemas import TokenData
from .utils import decode_token


class TokenBearer(OAuth2PasswordBearer):
    def __init__(self, token_url=settings.token_bearer_url):
        super().__init__(tokenUrl=token_url)

    async def __call__(self, request: Request) -> TokenData:
        token = await super().__call__(request)
        if token is None:
            raise HTTPException(status_code=401, detail="Invalid Token")
        token_data = decode_token(token)
        if token_data is None:
            raise HTTPException(status_code=401, detail="Invalid Token")
        self.verify_token_type(token_data.refresh)

        return token_data

    @staticmethod
    def verify_token_type(is_refresh: bool) -> None:
        raise NotImplementedError("Please Override this method in child classes")


class AccessTokenBearer(TokenBearer):
    @staticmethod
    def verify_token_type(is_refresh: bool) -> None:
        if is_refresh:
            raise HTTPException(status_code=401, detail="Access token required")


AccessTokenBearerDep = Annotated[TokenData, Depends(AccessTokenBearer())]


class RefreshTokenBearer(TokenBearer):
    @staticmethod
    def verify_token_type(is_refresh: bool) -> None:
        if not is_refresh:
            raise HTTPException(status_code=401, detail="Refresh token required")


RefreshTokenBearerDep = Annotated[TokenData, Depends(RefreshTokenBearer())]


async def get_current_user(token_data: AccessTokenBearerDep, session: SessionDep) -> User:
    user_email = token_data.user.email
    current_user = await user_service.get_user_by_email(user_email, session)
    if current_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Your account is not active")
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Your account is not verified")

    return current_user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
OAuth2PasswordRequestFormDep = Annotated[OAuth2PasswordRequestForm, Depends()]


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, tenant_id: UUID, current_user: User = Depends(get_current_user), session: SessionDep = None) -> bool:
        if session is None:
            raise HTTPException(status_code=500, detail="Database session is missing")

        result = await session.execute(
            select(TenantUser).where(
                TenantUser.user_id == current_user.id,
                TenantUser.tenant_id == tenant_id
            )
        )
        tenant_user = result.scalar_one_or_none()

        if not tenant_user:
            raise HTTPException(status_code=403, detail="You do not have access to this tenant")
            
        if tenant_user.role not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Operation not permitted for your role")
            
        return True
