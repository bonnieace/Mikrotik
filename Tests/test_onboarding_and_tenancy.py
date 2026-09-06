from __future__ import annotations

import pytest
from fastapi import HTTPException

from database.models import AdminUser, Router
from schemas import RouterOnboardingRequest
from security import is_encrypted
from services import onboarding_service
from services.onboarding_service import claim_onboarding, create_onboarding
from services.router_service import get_router_for_user


def _user(db, username: str, role: str = "isp") -> AdminUser:
    row = AdminUser(username=username, hashed_password="not-used", role=role)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_onboarding_is_safe_scoped_and_idempotent(db, monkeypatch):
    user = _user(db, "isp-one")
    token = "claim-token-with-more-than-thirty-two-characters"
    monkeypatch.setattr(onboarding_service, "random_token", lambda: token)
    provisioned = {}
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: True)
    monkeypatch.setattr(
        onboarding_service,
        "provision_l2tp_peer",
        lambda username, password: provisioned.update(username=username, password=password) or "10.77.0.12",
    )
    response = create_onboarding(
        RouterOnboardingRequest(name="Branch Router", portal_slug="branch-router", payment_provider="mpesa"),
        user,
    )
    script = response["script"]
    assert "/system backup save" in script
    assert "add-default-route=no" in script
    assert "use-peer-dns=no" in script
    assert "allow=mschap2" in script
    assert "allow=pap" not in script
    assert "uzanet-managed" in script
    assert "reset-configuration" not in script
    assert response["l2tp_peer"]["password"] not in repr(response["router"])
    assert response["l2tp_peer"]["provisioned"] is True
    assert response["l2tp_peer"]["ip_address"] == "10.77.0.12"
    assert provisioned["username"] == response["l2tp_peer"]["username"]

    router = db.query(Router).filter(Router.uid == response["router"]["uid"]).first()
    assert is_encrypted(router.password)
    assert token not in router.password

    first = claim_onboarding(token, "10.77.0.12/32", "7.15.3")
    second = claim_onboarding(token, "10.77.0.12/32", "7.15.3")
    assert first == second == {"status": "claimed", "router_uid": router.uid}


def test_router_lookup_hides_other_tenants_router(db):
    owner = _user(db, "owner")
    stranger = _user(db, "stranger")
    router = Router(
        name="Private",
        ip_address="10.77.0.9",
        username="api-user",
        password="encrypted-placeholder",
        owner_id=owner.id,
        portal_slug="private-router",
    )
    db.add(router)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        get_router_for_user(router.uid, stranger)
    assert exc.value.status_code == 404
