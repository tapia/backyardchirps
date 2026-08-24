"""
Django's command-line utility, living inside the package so that it is importable.

An installed station has no checkout and therefore no manage.py at a known path, so the
units and the maintainer scripts call the backyardchirps-manage console script, which
lands here. The manage.py in the repository root is a shim over this same function.
"""

import os
import sys


def main() -> None:
    """
    Run administrative tasks.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backyardchirps.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
