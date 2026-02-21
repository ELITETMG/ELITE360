import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/ftth")
SECRET_KEY = os.environ.get("SECRET_KEY", "ftth-contractor-platform-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
MAPBOX_PUBLIC_TOKEN = os.environ.get("MAPBOX_PUBLIC_TOKEN", "")
