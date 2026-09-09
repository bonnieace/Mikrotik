from __future__ import annotations

from database.models import AdminUser
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

    # hAP lite / RouterOS 6.49.17 does not expose /file copy. Check executable
    # RouterOS lines rather than comments so this catches a real command regression.
    assert "/file copy" not in executable
    assert "http-max-redirect-count" not in executable
    assert "html-directory-override=$managedDir" not in executable
