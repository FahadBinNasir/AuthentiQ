from fastapi import HTTPException

from app.main import health, current_session, password_hash, password_matches, read_invitation


def test_health_endpoint():
    assert health() == {"status": "ok", "service": "authentiq-api"}


def test_password_hash_is_not_plaintext():
    stored = password_hash("correct horse battery staple")
    assert stored != "correct horse battery staple"
    assert password_matches("correct horse battery staple", stored)
    assert not password_matches("wrong password", stored)


def test_workspace_requires_session():
    try:
        current_session(None)
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("A missing session must be rejected")


def test_invitation_does_not_expose_private_events_for_unknown_token():
    try:
        read_invitation("not-a-real-token")
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("An unknown invitation must be rejected")
