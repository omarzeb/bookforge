"""
Jobs routes — status polling and SSE streaming.

GET  /jobs/{id}        → current job status + output so far
GET  /jobs/{id}/stream → SSE stream of job progress
"""

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models import Job, JobStatus, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobResponse(BaseModel):
    id: str
    book_id: str
    task_name: str
    status: JobStatus
    streamed_output: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


async def _get_job_for_user(
    job_id: str,
    db: AsyncSession,
    user: User,
) -> Job:
    """Fetch a job and verify the user owns the associated book."""
    from app.db.models import Book
    result = await db.execute(
        select(Job)
        .join(Book, Job.book_id == Book.id)
        .where(Job.id == job_id, Book.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Job:
    return await _get_job_for_user(job_id, db, user)


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE endpoint — streams job progress as the worker generates output.

    Polls the job table every 500ms and pushes any new content.
    Closes when the job reaches DONE or FAILED.

    SSE format:
        data: {"status": "running", "delta": "new text chunk"}\n\n
    """
    # Verify ownership before streaming
    await _get_job_for_user(job_id, db, user)

    async def event_generator():
        import json
        last_length = 0
        poll_interval = 0.5  # seconds
        max_polls = 1800  # 15 minutes max (1800 × 0.5s)
        polls = 0

        while polls < max_polls:
            polls += 1
            await asyncio.sleep(poll_interval)

            # Re-fetch job fresh each poll
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if not job:
                yield f"data: {json.dumps({'status': 'error', 'delta': 'Job not found'})}\n\n"
                break

            output = job.streamed_output or ""
            delta = output[last_length:]
            last_length = len(output)

            if delta or job.status in (JobStatus.DONE, JobStatus.FAILED):
                payload = {
                    "status": job.status.value,
                    "delta": delta,
                }
                if job.status == JobStatus.FAILED:
                    payload["error"] = job.error_message or "Unknown error"

                yield f"data: {json.dumps(payload)}\n\n"

            if job.status in (JobStatus.DONE, JobStatus.FAILED):
                yield f"data: {json.dumps({'status': job.status.value, 'delta': '', 'done': True})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
