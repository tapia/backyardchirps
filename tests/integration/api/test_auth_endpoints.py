from typing import Any

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_me_anonymous(api_client: APIClient) -> None:
    response = api_client.get("/api/auth/me/")

    assert response.status_code == 200
    assert response.data["is_authenticated"] is False
    assert "csrf_token" in response.data


def test_me_authenticated(auth_client: APIClient) -> None:
    response = auth_client.get("/api/auth/me/")

    assert response.status_code == 200
    assert response.data["is_authenticated"] is True
    assert response.data["username"] == "user"
    assert response.data["is_staff"] is False
    assert "csrf_token" in response.data


def test_login_valid_credentials(api_client: APIClient, django_user_model: Any) -> None:
    django_user_model.objects.create_user(username="bob", password="s3cret-pw")

    response = api_client.post("/api/auth/login/", {"username": "bob", "password": "s3cret-pw"}, format="json")

    assert response.status_code == 200
    assert response.data["is_authenticated"] is True
    assert response.data["username"] == "bob"


def test_login_invalid_credentials(api_client: APIClient, django_user_model: Any) -> None:
    django_user_model.objects.create_user(username="bob", password="s3cret-pw")

    response = api_client.post("/api/auth/login/", {"username": "bob", "password": "wrong"}, format="json")

    assert response.status_code == 401
    assert "error" in response.data


def test_logout(auth_client: APIClient) -> None:
    assert auth_client.post("/api/auth/logout/").status_code == 204
