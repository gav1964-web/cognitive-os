import asyncio
from pathlib import Path

QUEUE: list[dict[str, str]] = []


async def handle_job(job: dict[str, str]) -> dict[str, str]:
    await asyncio.sleep(0)
    return {"job_id": job["id"], "status": "done"}


def save_status(result: dict[str, str]) -> None:
    Path("status.log").write_text(str(result), encoding="utf-8")


async def worker_loop() -> None:
    while QUEUE:
        job = QUEUE.pop(0)
        try:
            result = await handle_job(job)
            save_status(result)
        except Exception:
            QUEUE.append(job)
            break
