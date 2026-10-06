"""
adapters/hive_deepfake.py — Hive Moderation API adapter (optional paid upgrade).

Enable by setting DEEPFAKE_PROVIDER=hive and HIVE_API_KEY=<your_key> in .env.
This adapter is NEVER loaded unless explicitly configured.
"""
from app.adapters.base_deepfake import DeepfakeDetector, DeepfakeResult
from app.config import settings


class HiveDeepfakeDetector(DeepfakeDetector):
    """
    Optional paid adapter: Hive Moderation AI deepfake detection API.
    Requires HIVE_API_KEY environment variable.
    """

    BASE_URL = "https://api.thehive.ai/api/v2/task/sync"

    async def detect(self, media_path: str, media_type: str) -> DeepfakeResult:
        if not settings.HIVE_API_KEY:
            raise ValueError("HIVE_API_KEY not set. Cannot use Hive deepfake adapter.")

        # Step 9: Implement Hive API call
        # https://docs.thehive.ai/docs/visual-moderation
        raise NotImplementedError("Hive adapter — implement in Step 9 if switching from local.")
