from fastapi import APIRouter, BackgroundTasks
import os
router = APIRouter()

@router.post('/ingest-sentinel')
async def ingest_sentinel(tile_t0_url: str, tile_t1_url: str, background_tasks: BackgroundTasks):
    # Schedules NBR diff job - in prod worker will download tiles and run pipeline
    job_id = 'job_' + os.urandom(6).hex()
    # background_tasks.add_task(run_nbr, tile_t0_url, tile_t1_url)
    return {'job_id': job_id, 'status':'queued'}

@router.post('/score')
async def score(evidence_ids: list):
    # placeholder scoring combining sources
    score = min(1.0, 0.3 * len(evidence_ids))
    return {'confidence': score}
