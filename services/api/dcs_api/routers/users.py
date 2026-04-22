"""User management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.password import hash_password
from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.tenant import Role, User, UserRole
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.user import RoleResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_USERS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[UserResponse]:
    """List users in the tenant."""
    # Count total
    count_query = select(User).where(User.tenant_id == user.tenant_id)
    count_result = await session.execute(count_query)
    total = len(list(count_result.scalars().all()))

    # Get paginated results
    offset = (page - 1) * page_size
    query = (
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(query)
    users = list(result.scalars().all())

    items = []
    for u in users:
        user_response = UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            is_active=u.is_active,
            is_owner=u.is_owner,
            last_login=u.last_login,
            created_at=u.created_at,
            updated_at=u.updated_at,
            roles=[ur.role.name for ur in u.user_roles],
        )
        items.append(user_response)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserResponse:
    """Get current user information."""
    query = (
        select(User)
        .where(User.id == user.user_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(query)
    db_user = result.scalar_one()

    return UserResponse(
        id=db_user.id,
        tenant_id=db_user.tenant_id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        is_active=db_user.is_active,
        is_owner=db_user.is_owner,
        last_login=db_user.last_login,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        roles=[ur.role.name for ur in db_user.user_roles],
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[RoleResponse]:
    """List available roles in the tenant."""
    query = select(Role).where(Role.tenant_id == user.tenant_id)
    result = await session.execute(query)
    roles = list(result.scalars().all())

    return [
        RoleResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            role_type=r.role_type.value,
            is_system=r.is_system,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in roles
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_USERS))],
) -> UserResponse:
    """Get user by ID."""
    query = (
        select(User)
        .where(User.id == user_id, User.tenant_id == user.tenant_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(query)
    db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=db_user.id,
        tenant_id=db_user.tenant_id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        is_active=db_user.is_active,
        is_owner=db_user.is_owner,
        last_login=db_user.last_login,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        roles=[ur.role.name for ur in db_user.user_roles],
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_USERS))],
) -> UserResponse:
    """Create a new user."""
    # Check email uniqueness within tenant
    existing = await session.execute(
        select(User).where(User.email == data.email, User.tenant_id == user.tenant_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists in tenant",
        )

    # Create user
    new_user = User(
        tenant_id=user.tenant_id,
        email=data.email,
        password_hash=hash_password(data.password) if data.password else None,
        first_name=data.first_name,
        last_name=data.last_name,
    )
    session.add(new_user)
    await session.flush()

    # Assign roles
    for role_id in data.role_ids:
        role = await session.get(Role, role_id)
        if role and role.tenant_id == user.tenant_id:
            user_role = UserRole(
                user_id=new_user.id,
                role_id=role_id,
                granted_by=user.user_id,
            )
            session.add(user_role)

    await session.flush()

    return UserResponse(
        id=new_user.id,
        tenant_id=new_user.tenant_id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        is_active=new_user.is_active,
        is_owner=new_user.is_owner,
        last_login=new_user.last_login,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        roles=[],
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_USERS))],
) -> UserResponse:
    """Update user."""
    query = (
        select(User)
        .where(User.id == user_id, User.tenant_id == user.tenant_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(query)
    db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apply only explicitly allowed fields
    ALLOWED_UPDATE_FIELDS = {"email", "first_name", "last_name", "is_active"}
    update_data = data.model_dump(exclude_unset=True, exclude={"role_ids"})
    for key, value in update_data.items():
        if key in ALLOWED_UPDATE_FIELDS:
            setattr(db_user, key, value)

    # Update roles if specified
    if data.role_ids is not None:
        # Remove existing roles
        for ur in db_user.user_roles:
            await session.delete(ur)

        # Add new roles
        for role_id in data.role_ids:
            role = await session.get(Role, role_id)
            if role and role.tenant_id == user.tenant_id:
                user_role = UserRole(
                    user_id=db_user.id,
                    role_id=role_id,
                    granted_by=user.user_id,
                )
                session.add(user_role)

    await session.flush()

    # Reload user with roles
    await session.refresh(db_user)
    query = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(query)
    db_user = result.scalar_one()

    return UserResponse(
        id=db_user.id,
        tenant_id=db_user.tenant_id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        is_active=db_user.is_active,
        is_owner=db_user.is_owner,
        last_login=db_user.last_login,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        roles=[ur.role.name for ur in db_user.user_roles],
    )
