import config


def get_secret(name: str) -> str:
    return config.get_secret(name)
