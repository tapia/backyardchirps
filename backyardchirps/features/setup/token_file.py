import hmac

from django.conf import settings


def exists() -> bool:
    return settings.SETUP_TOKEN_FILE.is_file()


def matches(candidate: str) -> bool:
    """
    Whether the candidate is the token on disk.

    Compared in constant time. The token is 32 random bytes, so guessing it is hopeless
    either way, but the comparison is on a route anyone on the network can reach and
    there is no reason to make it leak how much of a guess was right.
    """
    try:
        stored = settings.SETUP_TOKEN_FILE.read_text().strip()
    except OSError:
        return False
    if not stored:
        return False
    return hmac.compare_digest(stored, candidate.strip())


def delete() -> None:
    """
    Throw the token away, which is what makes setup one-time. Missing already is fine.
    """
    settings.SETUP_TOKEN_FILE.unlink(missing_ok=True)
