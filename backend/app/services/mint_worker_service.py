from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.config import settings
from app.services.mint_job_service import run_next_job


logger = logging.getLogger(__name__)


def mint_worker_enabled() -> bool:
    return bool(settings.nft_mint_enabled and settings.nft_mint_worker_enabled)


async def run_controlled_mint_worker(stop_event: asyncio.Event) -> None:
    """Execute only jobs that a CEO has explicitly placed in the mint queue."""

    if not mint_worker_enabled():
        return

    worker_id = f"mint-worker-{os.getpid()}"
    idle_delay = max(2, int(settings.nft_mint_worker_poll_seconds))
    logger.info("Controlled NFT mint worker started as %s.", worker_id)

    while not stop_event.is_set():
        delay = idle_delay
        try:
            result: dict[str, Any] = await asyncio.to_thread(run_next_job, worker_id)
            if result.get("status") != "idle":
                delay = 1
        except Exception:
            logger.exception("Controlled NFT mint worker iteration failed.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            continue

    logger.info("Controlled NFT mint worker stopped.")
