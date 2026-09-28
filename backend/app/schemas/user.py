from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Публічна реєстрація.

    `role` тут немає свідомо. Раніше поле було тут і register довіряв йому,
    тому будь-хто міг надіслати {"role": "admin"} і отримати адміна без
    жодного доступу. Роль призначає або сівач при старті
    (`services/seed.py`), або адмін через `PATCH /api/v1/users/{id}/role`.
    """

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RoleUpdate(BaseModel):
    role: str
