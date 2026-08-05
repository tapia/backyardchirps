from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.shared.http import request_body


@api_view(["GET"])
@permission_classes([AllowAny])
def me(request: Request) -> Response:
    """
    Who is logged in, and a fresh CSRF token. The frontend keeps the token and sends it
    back as X-CSRFToken on every request that changes something.
    """
    csrf_token = get_token(request)
    if not request.user.is_authenticated:
        return Response({"is_authenticated": False, "csrf_token": csrf_token})
    return Response(
        {
            "is_authenticated": True,
            "username": request.user.username,
            "is_staff": request.user.is_staff,
            "csrf_token": csrf_token,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request: Request) -> Response:
    """
    Log in with a username and password. The CSRF token that comes back belongs to the
    new session, so the old one must be replaced with it.
    """
    body = request_body(request)
    username = body.get("username", "")
    password = body.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=401)
    login(request, user)
    return Response(
        {
            "is_authenticated": True,
            "username": user.username,
            "is_staff": user.is_staff,
            "csrf_token": get_token(request),
        }
    )


@api_view(["POST"])
def logout_view(request: Request) -> Response:
    """
    End the current session.
    """
    logout(request)
    return Response(status=204)
