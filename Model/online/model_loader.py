"""
model_loader.py
===============
Layer 1 — Keras model loader and inference runner.
Loads the 'disease_model.keras' once at startup and exposes a predict() method.
"""

import os
import io
import logging
import numpy as np
from typing import List, Tuple, Optional, Any
from PIL import Image, ImageStat

# Suppress TF logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf

logger = logging.getLogger(__name__)

# ── 3 Cattle Disease class names ─────
CLASS_NAMES: List[str] = [
    "Anthrax",
    "Foot_and_Mouth_Disease",
    "Healthy_Cattle",
]

class CattleDiseaseModel:
    """
    Singleton model loader.
    Loads Keras model and runs inference.
    """

    def __init__(self, model_path: str = "disease_model.keras"):
        # Search for model file
        actual_path = model_path
        if not os.path.exists(actual_path):
            # Try looking in root from Model/online/
            root_path = os.path.join(os.path.dirname(__file__), "..", "..", "disease_model.keras")
            if os.path.exists(root_path):
                actual_path = root_path
        
        logger.info(f"🔧 Loading Keras model from: {actual_path}")
        try:
            self.model = tf.keras.models.load_model(actual_path)
            # Warmup
            self.model.predict(np.zeros((1, 256, 256, 3)), verbose=0)
            logger.info(f"✅ Model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise e

    def validate_image(self, image: Image.Image) -> Tuple[bool, str]:
        """
        Heuristic image quality validation.
        Checks if the image is too dark or too light.
        """
        img = image.convert('RGB')
        stat = ImageStat.Stat(img)
        
        # Darkness/Brightness check (0-255 scale)
        brightness = stat.mean[0] * 0.299 + stat.mean[1] * 0.587 + stat.mean[2] * 0.114
        if brightness < 40:
            return False, "Image is too dark. Please provide a well-lit photo."
        if brightness > 230:
            return False, "Image is too bright. Please avoid direct glare."

        return True, "OK"

    def predict(
        self,
        image_bytes: bytes,
        top_k: int = 3,
    ) -> Tuple[str, float, List[dict], str]:
        """
        Run inference on raw image bytes.
        """
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Validate quality
        is_valid, status_msg = self.validate_image(image)

        # Preprocess
        img_resized = image.resize((256, 256))
        img_array = np.array(img_resized) / 255.0
        img_batch = np.expand_dims(img_array, axis=0)

        # Inference
        predictions = self.model.predict(img_batch, verbose=0)[0]
        indices = np.argsort(predictions)[::-1]
        
        k = min(top_k, len(CLASS_NAMES))
        top_indices = indices[:k]

        disease_key = CLASS_NAMES[top_indices[0]]
        confidence  = float(predictions[top_indices[0]])

        top_k_results = [
            {
                "rank":        i + 1,
                "disease_key": CLASS_NAMES[top_indices[i]],
                "confidence":  round(float(predictions[top_indices[i]]) * 100, 2),
            }
            for i in range(k)
        ]

        return disease_key, confidence, top_k_results, status_msg

# ── Singleton ─────────────────────────────────────────────────────
_model_instance: Optional[CattleDiseaseModel] = None

def get_model(model_path: Optional[str] = None) -> CattleDiseaseModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = CattleDiseaseModel(model_path or "disease_model.keras")
    return _model_instance
