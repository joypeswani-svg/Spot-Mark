"""
adapters/local_deepfake.py — Default local deepfake detector.

Uses a pretrained HuggingFace model (Xception/EfficientNet fine-tuned on
FaceForensics++ / DFDC / Celeb-DF).

Step 9: Full model loading and inference implemented here.
Step 1–8: Returns a metadata-only heuristic result as a placeholder.
"""
from app.adapters.base_deepfake import DeepfakeDetector, DeepfakeResult


class LocalDeepfakeDetector(DeepfakeDetector):
    """
    Self-hosted deepfake detector using open HuggingFace checkpoints.
    No API key required — runs locally on CPU (slow) or GPU (fast).

    Model download happens at worker startup via transformers.pipeline()
    and is cached in the shared ml/models/ Docker volume.
    """

    def __init__(self):
        # Step 9: Load model
        # from transformers import pipeline
        # self.classifier = pipeline(
        #     "image-classification",
        #     model="prithivMLmods/Deep-Fake-Detector-v2-Model",
        #     device="cpu",
        # )
        pass

    async def detect(self, media_path: str, media_type: str) -> DeepfakeResult:
        """
        Step 9: Real inference.
        Step 1–8: Returns metadata-only heuristic (EXIF anomaly check).
        """
        # Metadata-only heuristic (cheap, no GPU needed)
        metadata_findings = await self._check_metadata(media_path, media_type)
        has_anomalies = len(metadata_findings) > 0

        return DeepfakeResult(
            manipulation_score=30 if has_anomalies else 10,
            is_flagged=False,  # Never flag based on metadata alone
            provider="local-metadata-only",
            confidence_range="10–30% confidence (insufficient data for full analysis)",
            explanation=(
                "Full deepfake model inference not yet enabled (Step 9). "
                "Metadata heuristic only."
            ),
            metadata_findings=metadata_findings,
        )

    async def _check_metadata(self, media_path: str, media_type: str) -> list[str]:
        """
        Step 8+: Check EXIF/metadata for common AI-generation indicators.
        Returns list of anomaly descriptions.
        """
        findings = []
        # Step 8: Implement EXIF parsing with piexif / exiftool
        # e.g. missing GPS when claimed location, wrong software tag, etc.
        return findings
