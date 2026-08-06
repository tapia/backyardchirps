from django.contrib.auth.models import User


def superuser_exists() -> bool:
    """
    Whether the station has an owner yet.
    """
    return User.objects.filter(is_superuser=True).exists()


def create_superuser(username: str, password: str) -> None:
    """
    The first admin account. Callers check that there is not one already: this only
    writes.
    """
    User.objects.create_superuser(username=username, password=password)
