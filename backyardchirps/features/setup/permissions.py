from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

# Set on the session by the claim endpoint. It says the caller proved they hold the token
# install.sh printed, which is the only credential a station has before it has an account.
SESSION_FLAG = "setup_authorised"


class IsSetupAuthorised(BasePermission):
    """
    Either the caller claimed the station with its token, or they are already an admin.

    Admins are allowed because these endpoints outlive the wizard: picking a microphone
    and reading its level is what the admin guide sends people to when the station stops
    hearing anything.
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        if request.session.get(SESSION_FLAG) is True:
            return True
        return bool(request.user and request.user.is_staff)
