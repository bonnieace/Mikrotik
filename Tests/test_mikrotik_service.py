from services.mikrotik_service import _upsert_router_user, routeros_duration


class FakeResource:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.updated = None
        self.added = None

    def __iter__(self):
        return iter(self.rows)

    def update(self, **values):
        self.updated = values

    def add(self, **values):
        self.added = values


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
