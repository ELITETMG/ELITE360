import os
import json


def _parse_cors_origins(value: str | None) -> list[str]:
    if not value:
        return ["*"]

    cleaned = value.strip()
    if not cleaned:
        return ["*"]

    if cleaned.startswith("["):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                origins = [str(item).strip() for item in parsed if str(item).strip()]
                if origins:
                    return origins
        except json.JSONDecodeError:
            pass

    origins = [item.strip() for item in cleaned.split(",") if item.strip()]
    return origins or ["*"]

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/ftth")
SECRET_KEY = os.environ.get("SECRET_KEY", "ftth-contractor-platform-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
MAPBOX_PUBLIC_TOKEN = os.environ.get("MAPBOX_PUBLIC_TOKEN", "")
CORS_ORIGINS = _parse_cors_origins(os.environ.get("CORS_ORIGINS"))
