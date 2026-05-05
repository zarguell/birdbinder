from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_url: str = "http://localhost:8000"
    api_keys: str = ""  # comma-separated
    cf_access_enabled: bool = False
    cf_team_domain: str = ""
    cf_aud_tag: Optional[str] = None  # optional, verify audience matches this Access app
    cf_verify_jwt: bool = False  # opt-in full JWT verification (RS256 + issuer + audience)
    ai_base_url: Optional[str] = None
    ai_model: str = "gpt-4o"
    ai_image_model: Optional[str] = None
    auth_debug: bool = False
    ai_api_key: Optional[str] = None
    birdbinder_id_prompt: Optional[str] = None
    card_style_name: str = "default"
    database_url: str = "sqlite+aiosqlite:///./data/birdbinder.db"
    storage_path: str = "./storage"
    ebird_api_key: Optional[str] = None
    git_sha: str = "dev"

    @property
    def parsed_api_keys(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    model_config = {"env_file": ".env", "env_prefix": ""}


settings = Settings()
