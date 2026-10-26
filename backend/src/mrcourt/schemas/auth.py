import uuid
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    role: Literal["advocate", "petitioner"]
    full_name: str = Field(min_length=1, max_length=200)
    # The sign-in name. Optional for older callers; the sign-up page always asks for it.
    username: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9._-]{2,29}$")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=10, max_length=200)
    bar_registration_number: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _needs_contact(self) -> Self:
        if not self.email and not self.phone:
            raise ValueError("Provide an email or a phone number")
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class OtpRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)


class OtpVerify(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    code: str = Field(pattern=r"^[0-9]{6}$")


class PhoneCode(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class ForgotPassword(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)


class ResetPassword(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=10, max_length=200)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: str
    whatsapp_reminders: bool
    hearing_alert_days: int
    theme: Literal["system", "light", "dark"]
    voice_consent: bool = False  # whether the person agreed to voice control; the time itself is not returned
    voice_cloud_opt_in: bool = False
    voice_language: str | None = None


class SettingsPatch(BaseModel):
    language: str | None = Field(default=None, max_length=8)
    whatsapp_reminders: bool | None = None
    hearing_alert_days: int | None = Field(default=None, ge=0, le=14)
    theme: Literal["system", "light", "dark"] | None = None
    voice_consent: bool | None = None
    voice_cloud_opt_in: bool | None = None
    voice_language: Literal["en-IN", "hi-IN", "ta-IN"] | None = None  # None clears the choice


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["advocate", "petitioner", "admin"]
    full_name: str
    username: str | None = None
    bar_registration_number: str | None
    phone: str | None
    phone_verified: bool = False
    verification_status: Literal["none", "pending", "verified"]
    is_admin: bool
    settings: SettingsOut


class MePatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    bar_registration_number: str | None = Field(default=None, max_length=64)


class DeactivateRequest(BaseModel):
    acknowledge_case_retention: Literal[True]


class PendingVerification(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    bar_registration_number: str | None


class VerificationDecision(BaseModel):
    decision: Literal["verified", "rejected"]
