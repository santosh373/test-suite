import json
import os

URLS_FILE = os.path.join(os.getcwd(), "urls.json")

# Read once at startup — changing ENV_NAME after the server starts has no effect.
_ENV_NAME: str = os.getenv("ENV_NAME", "")


def load_urls() -> dict:
    """Returns {env_name: {service: base_url}}"""
    try:
        with open(URLS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_environments() -> list:
    return list(load_urls().keys())


def get_active_env() -> str:
    if _ENV_NAME:
        return _ENV_NAME
    envs = get_environments()
    return envs[0] if envs else ""


def get_services() -> list:
    """All service/type keys across every environment."""
    seen = {}
    for services in load_urls().values():
        for k in services:
            seen[k] = True
    return list(seen.keys())


def get_base_url(env_name: str, service: str) -> str:
    return load_urls().get(env_name, {}).get(service, "").rstrip("/")
