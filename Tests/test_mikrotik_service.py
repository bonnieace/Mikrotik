import pytest
from fastapi import HTTPException

from services.mikrotik_service import (
    _monitor_traffic_once,
    _refresh_managed_hotspot_login,
    _traffic_interface,
    _upsert_router_user,
    routeros_duration,
)


class FakeResource:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.updated = None
        self.updates = []
        self.added = None
        self.called = None

    def __iter__(self):
        return iter(self.rows)

    def __call__(self, command, **kwargs):
        self.called = (command, kwargs)
        return iter([{'rx-bits-per-second': 123, 'tx-bits-per-second': 456}])

    def update(self, **values):
        self.updated = values
        self.updates.append(values)

    def add(self, **values):
        self.added = values


class FakeApi:
    def __init__(self, interfaces):
        self.interfaces = interfaces
        self.interface_resource = FakeResource(interfaces)

    def path(self, *parts):
        assert parts == ("interface",)
        return self.interface_resource


class FakeRouterApi:
    def __init__(self, resources):
        self.resources = resources

    def path(self, *parts):
        return self.resources[parts]


def test_routeros_upsert_uses_installed_client_shape():
    existing = FakeResource([{'.id': '*7', 'name': 'voucher'}])
    _upsert_router_user(existing, 'voucher', 'secret-value', 'paid', '01:00:00')
    assert existing.updated == {
        '.id': '*7',
        'name': 'voucher',
        'password': 'secret-value',
        'profile': 'paid',
        'disabled': 'no',
        'limit-uptime': '01:00:00',
    }

    new = FakeResource()
    _upsert_router_user(new, 'new-user', 'secret-value', 'paid', None)
    assert new.added['name'] == 'new-user'
    assert 'limit-uptime' not in new.added
    assert routeros_duration(1500) == '1d01:00:00'


def test_create_only_routeros_user_never_overwrites_existing_identity():
    existing = FakeResource([{'.id': '*7', 'name': 'voucher'}])
    with pytest.raises(HTTPException) as exc:
        _upsert_router_user(
            existing,
            'voucher',
            'new-secret',
            'paid',
            '01:00:00',
            replace_existing=False,
        )
    assert exc.value.status_code == 409
    assert existing.updated is None
    assert existing.added is None


def test_prepared_routeros_user_can_be_created_disabled():
    resource = FakeResource()
    _upsert_router_user(
        resource,
        'prepared',
        'secret-value',
        'paid',
        '01:00:00',
        enabled=False,
    )
    assert resource.added['disabled'] == 'yes'


def test_traffic_interface_prefers_named_bridge_then_running_bridge():
    assert _traffic_interface(
        FakeApi([
            {'name': 'ether1', 'type': 'ether', 'running': 'true'},
            {'name': 'bridge', 'type': 'bridge', 'running': 'false'},
        ])
    ) == 'bridge'

    assert _traffic_interface(
        FakeApi([
            {'name': 'ether1', 'type': 'ether', 'running': 'true'},
            {'name': 'br-lan', 'type': 'bridge', 'running': 'true'},
        ])
    ) == 'br-lan'


def test_traffic_interface_falls_back_to_running_interface():
    assert _traffic_interface(
        FakeApi([
            {'name': 'lo', 'type': 'loopback', 'running': 'true'},
            {'name': 'ether5', 'type': 'ether', 'running': 'true'},
        ])
    ) == 'ether5'


def test_monitor_traffic_uses_once_as_argument_not_subcommand():
    api = FakeApi([{'name': 'br-lan', 'type': 'bridge', 'running': 'true'}])
    rows = _monitor_traffic_once(api, 'br-lan')

    assert rows[0]['rx-bits-per-second'] == 123
    assert api.interface_resource.called == (
        'monitor-traffic',
        {'interface': 'br-lan', 'once': ''},
    )


def _portal_api(files, *, servers=None, profiles=None):
    file_resource = FakeResource(files)
    return FakeRouterApi({
        ("ip", "hotspot"): FakeResource(servers or [{"profile": "default", "disabled": "no"}]),
        ("ip", "hotspot", "profile"): FakeResource(
            profiles or [{"name": "default", "html-directory": "hotspot"}]
        ),
        ("file",): file_resource,
    }), file_resource


def test_portal_refresh_updates_only_backup_proven_login_page():
    api, files = _portal_api([
        {".id": "*1", "name": "hotspot/login.html", "contents": "original"},
        {".id": "*2", "name": "hotspot/login-pre-uzanet.txt", "contents": "backup"},
        {".id": "*3", "name": "hotspot/status.html", "contents": "status"},
    ])

    result = _refresh_managed_hotspot_login(api, "new portal", "12345678-abcd")

    assert result == {"files_updated": 1, "profiles_updated": 1}
    assert files.updates == [{".id": "*1", "contents": "new portal"}]


def test_portal_refresh_recognizes_legacy_managed_directory():
    managed_dir = "hotspot-uzanet-12345678"
    api, files = _portal_api(
        [{".id": "*7", "name": f"{managed_dir}/login.html", "contents": "legacy"}],
        profiles=[{
            "name": "default",
            "html-directory": "hotspot",
            "html-directory-override": managed_dir,
        }],
    )

    _refresh_managed_hotspot_login(api, "new portal", "12345678-abcd")

    assert files.updates == [{".id": "*7", "contents": "new portal"}]


def test_portal_refresh_recognizes_embedded_ownership_marker():
    api, files = _portal_api([
        {".id": "*9", "name": "hotspot/login.html", "contents": '<meta name="uzanet-managed-portal">'},
    ])

    _refresh_managed_hotspot_login(api, "new portal", "12345678-abcd")

    assert files.updates == [{".id": "*9", "contents": "new portal"}]


def test_portal_refresh_rejects_unrelated_custom_login_page():
    api, files = _portal_api([
        {".id": "*1", "name": "hotspot/login.html", "contents": "custom ISP portal"},
    ])

    with pytest.raises(HTTPException) as exc:
        _refresh_managed_hotspot_login(api, "new portal", "12345678-abcd")

    assert exc.value.status_code == 409
    assert exc.value.detail == "No Uzanet-managed HotSpot login page was found"
    assert files.updates == []


def test_portal_refresh_requires_enabled_hotspot_server():
    api, files = _portal_api(
        [{".id": "*1", "name": "hotspot/login.html", "contents": "uzanet-managed-portal"}],
        servers=[{"profile": "default", "disabled": "yes"}],
    )

    with pytest.raises(HTTPException) as exc:
        _refresh_managed_hotspot_login(api, "new portal", "12345678-abcd")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Router has no enabled HotSpot server"
    assert files.updates == []
