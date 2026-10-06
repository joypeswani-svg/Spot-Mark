"""tasks/video_task.py — Async deepfake video analysis (Step 9)"""
from app.tasks.celery_app import celery_app

@celery_app.task(bind=True, name="tasks.analyze_video")
def analyze_video_task(self, video_url: str, job_id: str):
    """Step 9: Download video, sample frames, run deepfake classifier."""
    # TODO Step 9: implement using pluggable adapter
    return {"status": "not_implemented", "job_id": job_id}
