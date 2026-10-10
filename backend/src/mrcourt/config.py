from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based settings. Secrets come only from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://mrcourt:mrcourt@localhost:5432/mrcourt"
    session_secret: str = ""
    session_max_age_seconds: int = 60 * 60 * 12
    cookie_secure: bool = True
    anthropic_api_key: str = ""
    embedding_api_key: str = ""  # unused; kept so older environment files still load
    voyage_api_key: str = ""  # meaning-based search (embeddings)
    embedding_model: str = "voyage-3.5"
    min_vector_score: float = 0.2  # a floor only: raw similarity cannot tell relevant from unrelated
    rerank_model: str = "rerank-2.5"
    min_rerank_score: float = 0.5  # what a meaning-only passage must score to be cited (measured, see quality-results)
    sarvam_api_key: str = ""  # speech to text for Indian languages
    stt_model: str = "saaras:v4"
    ocr_languages: str = "eng+tam"  # Tesseract language packs, joined with +
    max_ocr_pages: int = 60
    whatsapp_provider_api_key: str = ""
    # Text messages through Twilio. A free trial account texts verified numbers by SMS, and the free
    # WhatsApp sandbox messages people who have joined it. Leave empty to use the development outbox.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key_sid: str = ""  # optional: an API key (SK...) and secret can be used instead of the auth token
    twilio_api_key_secret: str = ""
    twilio_sms_from: str = ""  # your Twilio phone number, e.g. +15005550006; empty turns SMS off
    twilio_whatsapp_from: str = ""  # the sandbox number, e.g. whatsapp:+14155238886; empty turns WhatsApp off
    fast2sms_api_key: str = ""  # Indian SMS service: codes use its OTP route, reminders its Quick SMS route
    fast2sms_whatsapp_phone_number_id: str = ""  # your WhatsApp Business number's id, from the Fast2SMS panel
    fast2sms_whatsapp_code_template: str = ""  # id of an approved template with one variable: the code
    fast2sms_whatsapp_reminder_template: str = ""  # id of an approved template with two variables: the case, then when
    fast2sms_otp_route: bool = False  # true only after Fast2SMS "website verification"; otherwise codes use Quick SMS
    sms_country_code: str = "91"
    whatsapp_phone_number_id: str = ""
    answer_model: str = "claude-sonnet-5-5"
    upload_dir: str = "uploads"
    max_upload_bytes: int = 15 * 1024 * 1024
    knowledge_dir: str = "knowledge"  # originals of uploaded knowledge documents
    max_knowledge_bytes: int = 10 * 1024 * 1024
    max_knowledge_pages: int = 600
    assistant_max_steps: int = 6
    assistant_model: str = ""  # empty means use answer_model
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    login_attempts_per_window: int = 10  # raised only for automated end-to-end runs
    min_retrieval_score: float = 0.3
    # Browser origins allowed to make state-changing requests, comma separated. Set this to the
    # public address of the frontend in production. Same-host requests are always allowed.
    allowed_origins: str = "http://localhost:5173"
    environment: str = "development"
    # Production: the built website (frontend/dist) is served by this app, so pages and API share one address.
    frontend_dist: str = ""
    # Minutes between hearing-reminder runs inside the app (0 = off; use an outside scheduler instead).
    reminder_interval_minutes: int = 0

    @field_validator("database_url")
    @classmethod
    def _driver(cls, value: str) -> str:
        """Hosts such as Render give postgres://... addresses; SQLAlchemy needs the psycopg driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

