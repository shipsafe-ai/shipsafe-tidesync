import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT: str = os.environ["GCP_PROJECT"]
GEMINI_MODEL: str = os.environ["GEMINI_MODEL"]
BQ_DATASET: str = os.environ.get("BQ_DATASET", "hormuz_port_arrivals")
FIVETRAN_ALLOW_WRITES: bool = os.environ.get("FIVETRAN_ALLOW_WRITES", "false").lower() == "true"
STALE_THRESHOLD_SECONDS: int = int(os.environ.get("STALE_THRESHOLD_SECONDS", "3600"))
TIDESYNC_PUBLIC_URL: str = os.environ.get("TIDESYNC_PUBLIC_URL", "")


@lru_cache(maxsize=32)
def get_secret(name: str) -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    path = f"projects/{GCP_PROJECT}/secrets/{name}/versions/latest"
    response = client.access_secret_version(name=path)
    return response.payload.data.decode("utf-8")


def fivetran_api_key() -> str:
    return get_secret("FIVETRAN_APIKEY")


def fivetran_api_secret() -> str:
    return get_secret("FIVETRAN_APISECRET")


def webhook_secret() -> str:
    return get_secret("WEBHOOK_SECRET")
