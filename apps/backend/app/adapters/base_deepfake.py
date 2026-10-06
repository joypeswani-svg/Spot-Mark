"""
adapters/base_deepfake.py — Abstract base for pluggable deepfake detection.

To add a new provider:
  1. Create a new file, e.g. adapters/hive_deepfake.py
  2. Subclass DeepfakeDetector and implement detect()
  3. Set DEEPFAKE_PROVIDER=hive in .env
  4. Register in get_deepfake_detector() below
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeepfakeResult:
    manipulation_score: int       # 0–100
    is_flagged: bool
    provider: str
    confidence_range: str         # e.g. "60–75% confidence (moderate)"
    explanation: str
    metadata_findings: list[str]


class DeepfakeDetector(ABC):
    """Abstract interface — all deepfake providers must implement this."""

    @abstractmethod
    async def detect(self, media_path: str, media_type: str) -> DeepfakeResult:
        """
        Analyze media for manipulation.

        Args:
            media_path: Local path to the media file.
            media_type: "image" | "video" | "audio"

        Returns:
            DeepfakeResult with score, confidence range, and explanation.

        IMPORTANT: Never claim certainty > 95%. Always return a confidence
        range, not an exact probability. UI must show "could not determine"
        on any exception rather than a false positive/negative.
        """
        ...


def get_deepfake_detector(provider: str = "local") -> DeepfakeDetector:
    """
    Factory: return the configured deepfake detector adapter.
    Configured via DEEPFAKE_PROVIDER env var.
    """
    if provider == "local":
        from app.adapters.local_deepfake import LocalDeepfakeDetector
        return LocalDeepfakeDetector()
    elif provider == "hive":
        from app.adapters.hive_deepfake import HiveDeepfakeDetector
        return HiveDeepfakeDetector()
    elif provider == "sensity":
        from app.adapters.sensity_deepfake import SensityDeepfakeDetector
        return SensityDeepfakeDetector()
    else:
        raise ValueError(f"Unknown deepfake provider: {provider}")
