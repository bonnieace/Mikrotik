from __future__ import annotations

import pytest
from fastapi import HTTPException

from database.models import AdminUser, Log, Router
from schemas import RouterOnboardingRequest
from services import onboarding_service
from services.onboarding_service import create_onboarding


def test_hotspot_redirect_uses_routeros6_file_syntax(db, monkeypatch):
    owner = AdminUser(username="isp-one", hashed_password="not-used", role="isp")
    db.add(owner)
    db.commit()
    db.refresh(owner)

    monkeypatch.setenv("PORTAL_PUBLIC_URL", "https://admin.uzanet.co.ke")
    monkeypatch.setattr(onboarding_service, "vpn_agent_enabled", lambda: False)

    bundle = create_onboarding(
        RouterOnboardingRequest(name="Branch Router", portal_slug="branch-router"),
        owner,
    )
    script = bundle["script"]
    executable = "\n".join(
        line for line in script.splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "https://admin.uzanet.co.ke/portal/isp-one/branch-router" in script
    assert "link-login-only-esc" in script
    assert "link-orig-esc" in script
    assert "mac-esc" in script
    assert "ip-esc" in script
    assert "login-pre-uzanet" in script
    assert "/file set $loginId contents=" in executable
    assert "Opening your internet portal" in script
    assert "Continue manually" in script
    assert "prefers-reduced-motion" in script
    assert "cdnjs" not in script

    # hAP lite / RouterOS 6.49.17 does not expose /file copy. Check executable
    # RouterOS lines rather than comments so this catches a real command regression.
    assert "/file copy" not in executable
    assert "http-max-redirect-count" not in executable
    assert "html-directory-override=$managedDir" not in executable


def test_portal_refresh_renders_current_template_and_writes_audit_log(db, monkeypatch):
    owner = AdminUser(username="isp-one", hashed_password="not-used", role="isp")
    db.add(owner)
    db.flush()
    router = Router(
        name="Branch Router",
        ip_address="10.77.0.9",
        username="api-user",
        password="encrypted-placeholder",
        owner_id=owner.id,
        portal_slug="branch-router",
        portal_enabled=True,
        onboarding_status="claimed",
    )
    db.add(router)
    db.commit()
    router_id = router.id
    router_uid = router.uid
    pushed = {}
    monkeypatch.setenv("PORTAL_PUBLIC_URL", "https://admin.uzanet.co.ke")
    monkeypatch.setattr(
        onboarding_service,
        "refresh_managed_hotspot_login",
        lambda received_id, html, received_uid: pushed.update(
            router_id=received_id,
            router_uid=received_uid,
            html=html,
        ) or {"files_updated": 1, "profiles_updated": 1},
    )

    result = onboarding_service.refresh_captive_portal(router_id)

    assert result == {
        "status": "refreshed",
        "router_uid": router_uid,
        "template_version": onboarding_service.PORTAL_TEMPLATE_VERSION,
        "files_updated": 1,
        "profiles_updated": 1,
    }
    assert pushed["router_id"] == router_id
    assert pushed["router_uid"] == router_uid
    assert "https://admin.uzanet.co.ke/portal/isp-one/branch-router" in pushed["html"]
    assert 'name="uzanet-managed-portal" content="1"' in pushed["html"]
    assert "Continue manually" in pushed["html"]
    log = db.query(Log).filter_by(router_id=router_id, event_type="router.portal.refreshed").one()
    assert log.description == "Captive portal template v1 refreshed"


def test_portal_refresh_requires_enabled_customer_portal(db, monkeypatch):
    owner = AdminUser(username="isp-one", hashed_password="not-used", role="isp")
    db.add(owner)
    db.flush()
    router = Router(
        name="Branch Router",
        ip_address="10.77.0.9",
        username="api-user",
        password="encrypted-placeholder",
        owner_id=owner.id,
        portal_slug="branch-router",
        portal_enabled=False,
        onboarding_status="claimed",
    )
    db.add(router)
    db.commit()
    monkeypatch.setattr(
        onboarding_service,
        "refresh_managed_hotspot_login",
        lambda *_args: pytest.fail("disabled portal must not contact the router"),
    )

    with pytest.raises(HTTPException) as exc:
        onboarding_service.refresh_captive_portal(router.id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Enable the customer portal before refreshing it"
