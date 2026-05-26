from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Webshake Trading"
    app_version: str = "v1.0 Clean Install Beta"
    paper_trading: bool = True
    database_url: str = "sqlite:///../database/webshake_trading.db"
    coinbase_api_key: str | None = None
    coinbase_api_secret: str | None = None
    coinbase_api_passphrase: str | None = None

    class Config:
        env_prefix = "WEBSHAKE_"
        env_file = ".env"
        extra = "ignore"

settings = Settings()
