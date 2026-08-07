from pydantic import BaseModel, EmailStr, Field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=72,
        description="Password must be between 8 and 72 characters")
    full_name: str
    company_name: str
    default_currency: str
    timezone: str = Field(
        default="UTC", description="IANA timezone name, e.g., 'America/New_York'"
    )

    @field_validator("timezone")
    @classmethod
    def validate_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(
                f"'{value}' is not a valid IANA timezone (e.g., 'UTC', 'America/New_York', 'Europe/London')"
            )
        return value


    

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True



