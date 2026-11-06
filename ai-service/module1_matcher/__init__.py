"""
Module 1 (SBERT + GNN Semantic Skill Matching & Dependency Weighting) Contract & Adapter.
Provides a pluggable boundary so the research SBERT+GNN implementation can be swapped in seamlessly.
"""

from .schemas import MatchPipelineRequest, Module1Output
from .extractor import Module1MatcherProtocol, DefaultModule1Extractor
from .router import router

__all__ = [
    "MatchPipelineRequest",
    "Module1Output",
    "Module1MatcherProtocol",
    "DefaultModule1Extractor",
    "router",
]
