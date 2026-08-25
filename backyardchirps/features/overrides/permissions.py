from typing import Any

from rest_framework.permissions import SAFE_METHODS
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsAdminUserOrReadOnly(BasePermission):
    """
    Anyone may read the per-species detection rules, only staff may change them.
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
