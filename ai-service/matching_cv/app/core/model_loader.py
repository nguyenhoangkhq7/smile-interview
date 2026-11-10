"""Singleton model loader and manager for machine learning models."""
import logging
import threading
from typing import Any, Optional
import torch
from sentence_transformers import SentenceTransformer

from matching_cv.app.core.config import settings

logger = logging.getLogger(__name__)


class ModelLoader:
    """Singleton class responsible for loading and holding ML models in memory."""

    _instance: Optional["ModelLoader"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelLoader":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._model: Optional[SentenceTransformer] = None
        self._models: dict[tuple[str, Optional[str]], SentenceTransformer] = {}
        self._resolved_revisions: dict[tuple[str, Optional[str]], Optional[str]] = {}
        self._device: str = self._resolve_device()
        self._model_name: str = settings.STAGE3_MODEL_NAME
        self._is_loaded: bool = False
        self._initialized: bool = True

    def _resolve_device(self) -> str:
        """Resolve target computation device (cuda vs cpu)."""
        target_device = settings.DEVICE.lower()
        if target_device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        elif target_device == "cuda":
            if torch.cuda.is_available():
                device = "cuda"
            else:
                logger.warning("CUDA was requested but is not available. Falling back to CPU.")
                device = "cpu"
        else:
            device = "cpu"

        logger.info(f"Target inference device resolved to: {device}")
        return device

    def load_model(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> SentenceTransformer:
        """Load a SentenceTransformer model into memory (RAM/VRAM) in evaluation mode."""
        target_model = model_name or self._model_name
        target_key = (target_model, revision)

        with self._lock:
            if target_key in self._models and self._models[target_key] is not None:
                logger.info(f"Model '{target_model}' (revision={revision}) is already loaded.")
                return self._models[target_key]

            logger.info(f"Loading embedding model '{target_model}' (revision={revision}) on device: {self._device}...")
            try:
                load_kwargs: dict[str, Any] = {"device": self._device}
                if revision:
                    load_kwargs["revision"] = revision
                loaded_model = SentenceTransformer(target_model, **load_kwargs)
                loaded_model.eval()  # Ensure evaluation mode
                self._models[target_key] = loaded_model

                # Determine resolved commit hash/revision
                resolved_rev = revision
                try:
                    if hasattr(loaded_model, "__getitem__") and len(loaded_model) > 0:
                        first_mod = loaded_model[0]
                        if hasattr(first_mod, "auto_model") and hasattr(first_mod.auto_model, "config"):
                            resolved_rev = getattr(first_mod.auto_model.config, "_commit_hash", revision) or revision
                except Exception:
                    resolved_rev = revision
                self._resolved_revisions[target_key] = resolved_rev

                if target_model == self._model_name and revision is None:
                    self._model = loaded_model
                    self._is_loaded = True
                logger.info(f"Model '{target_model}' (resolved_revision={resolved_rev}) loaded successfully on {self._device}.")
                return loaded_model
            except Exception as e:
                logger.error(f"Failed to load model '{target_model}': {str(e)}", exc_info=True)
                raise e

    def get_model(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> SentenceTransformer:
        """Retrieve the loaded SentenceTransformer instance, loading on-demand if necessary."""
        target_model = model_name or self._model_name
        target_key = (target_model, revision)

        if target_key not in self._models or self._models[target_key] is None:
            logger.warning(
                f"Model '{target_model}' (revision={revision}) requested before initialization. Attempting on-demand load..."
            )
            self.load_model(target_model, revision=revision)

        model = self._models.get(target_key)
        if model is None:
            raise RuntimeError(f"Model '{target_model}' (revision={revision}) is not initialized and could not be loaded.")
        return model

    def get_model_dimension(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> int:
        """Return embedding dimension for the specified model."""
        model = self.get_model(model_name, revision)
        if hasattr(model, "get_embedding_dimension"):
            return int(model.get_embedding_dimension())
        if hasattr(model, "get_sentence_embedding_dimension"):
            return int(model.get_sentence_embedding_dimension())
        return 768

    def get_max_seq_length(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> int:
        """Return maximum sequence length for the specified model."""
        model = self.get_model(model_name, revision)
        return int(getattr(model, "max_seq_length", 128))

    def get_tokenizer(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Any:
        """Return tokenizer for the specified model."""
        model = self.get_model(model_name, revision)
        return getattr(model, "tokenizer", None)

    def get_resolved_revision(
        self,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Optional[str]:
        """Return resolved immutable revision commit hash for the specified model."""
        target_model = model_name or self._model_name
        target_key = (target_model, revision)
        if target_key not in self._models:
            self.load_model(target_model, revision=revision)
        return self._resolved_revisions.get(target_key, revision)

    @property
    def device(self) -> str:
        """Current inference device."""
        return self._device

    @property
    def model_name(self) -> str:
        """Name of the currently configured model."""
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        """Check if default model is currently loaded in memory."""
        return (self._is_loaded and self._model is not None) or len(self._models) > 0

    def get_info(self) -> dict[str, Any]:
        """Return diagnostic details regarding model status."""
        return {
            "model_name": self._model_name,
            "device": self._device,
            "is_loaded": self.is_loaded,
            "cuda_available": torch.cuda.is_available(),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "loaded_models": [
                {
                    "model_name": k[0],
                    "configured_revision": k[1],
                    "resolved_revision": self._resolved_revisions.get(k),
                }
                for k in self._models.keys()
            ],
        }


# Global singleton instance
model_loader = ModelLoader()
