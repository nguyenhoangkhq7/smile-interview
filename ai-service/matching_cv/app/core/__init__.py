"""Core module containing configurations, model loaders, and system constants."""
from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import model_loader

__all__ = ["settings", "model_loader"]
