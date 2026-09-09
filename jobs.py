"""Singleton background worker for access expiry and payment reconciliation."""

from __future__ import annotations

import asyncio
import logging
import os

from services.access_service import cleanup_failed_prepared_hotspot_sessions
from services.maintenance_service import expire_access
from services.onboarding_service import expire_onboarding_downloads
from services.payment_service import expire_payment_sessions, reconcile_pending_payments
from settings import get_settings


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("uzanet.jobs")


async def run() -> None:
    settings = get_settings()
    settings.validate()
    interval = max(30, int(os.getenv("JOB_INTERVAL_SECONDS", "60")))
    while True:
        try:
            await asyncio.to_thread(expire_onboarding_downloads)
            expired_payments = await asyncio.to_thread(expire_payment_sessions)
            reconciliation = await reconcile_pending_payments()
            prepared_cleanup = await asyncio.to_thread(cleanup_failed_prepared_hotspot_sessions)
            access = await asyncio.to_thread(expire_access)
            logger.info(
                "maintenance_complete expired_payments=%s reconciled=%s prepared_cleanup=%s access=%s",
                expired_payments,
                reconciliation,
                prepared_cleanup,
                access,
            )
        except Exception:
            logger.exception("maintenance_failed")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run())
