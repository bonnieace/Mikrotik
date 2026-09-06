"""Idempotent maintenance jobs intended for an external minute-level scheduler."""

from __future__ import annotations

from datetime import datetime

from database.models import HotspotUser, PPPUser
from database.session import SessionLocal
from services.mikrotik_service import set_hotspot_enabled, set_pppoe_enabled


def expire_access() -> dict:
    db = SessionLocal()
    now = datetime.utcnow()
    disabled = 0
    failed = 0
    try:
        hotspot_rows = db.query(HotspotUser).filter(HotspotUser.is_active.is_(True), HotspotUser.expires_at <= now).all()
        pppoe_rows = db.query(PPPUser).filter(PPPUser.is_active.is_(True), PPPUser.expires_on <= now).all()
        for row in hotspot_rows:
            try:
                set_hotspot_enabled(row.router_id, row.otp, False)
                row.is_active = False
                disabled += 1
            except Exception:
                failed += 1
        for row in pppoe_rows:
            try:
                set_pppoe_enabled(row.router_id, row.pppoe_username, False)
                row.is_active = False
                disabled += 1
            except Exception:
                failed += 1
        db.commit()
        return {"checked": len(hotspot_rows) + len(pppoe_rows), "disabled": disabled, "failed": failed}
    finally:
        db.close()

