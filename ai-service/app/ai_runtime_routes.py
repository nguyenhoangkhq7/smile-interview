"""Internal configuration metadata. Provider credentials are never returned."""
import os

from fastapi import APIRouter, HTTPException, Request

from adaptive_questioning.evidence.policy_config import configured_policy
from app.ai_runtime import TOKEN_HEADER, authorized, credential, model_value, policy_value
from matching_cv.app.core.config import settings as matching
from matching_cv.app.core.model_loader import model_loader
from skill_gap.adapters.config import load_config
from voice.routes import settings as voice_settings

router = APIRouter(prefix="/internal/runtime", include_in_schema=False)


def _configuration(request: Request) -> dict:
    if not authorized(request.headers.get(TOKEN_HEADER)):
        raise HTTPException(status_code=401)
    skill_gap = load_config()
    voice = voice_settings()
    policy = configured_policy()
    embedding = matching.STAGE3_MODEL_NAME
    revision = matching.STAGE3_MODEL_REVISION
    return {
        "settings": {
            "models": {
                "interviewModel": model_value("interviewModel", os.getenv("OPENROUTER_MODEL", "qwen/qwen3.7-flash")),
                "fastModel": model_value("fastModel", os.getenv("OPENROUTER_FAST_MODEL", "").strip()),
                "matchingModel": matching.OPENROUTER_MODEL,
                "verifierModel": model_value("verifierModel", os.getenv("OPENROUTER_VERIFIER_MODEL") or matching.OPENROUTER_VERIFIER_MODEL),
                "skillGapModel": model_value("skillGapModel", skill_gap.llm.model),
                "embeddingModel": embedding,
                "embeddingRevision": revision or "",
                "sttModel": voice["stt_model"],
                "ttsModel": voice["tts_model"],
                "ttsVoice": voice["voice"],
                "ttsFormat": voice["format"],
                "ttsSampleRate": voice["sample_rate"],
                "simliFaceId": model_value("simliFaceId", os.getenv("SIMLI_FACE_ID", "").strip()),
            },
            "policy": {
                "coreImportance": policy.core_importance, "fallbackDepth": policy.fallback_depth,
                "reserveFollowupFraction": policy.reserve_followup_fraction,
                "minFailureContexts": policy.min_failure_contexts,
                "allowExtensionProbes": policy.allow_extension_probes,
                "maxQuestions": policy_value("maxQuestions", 40),
                "durationSeconds": policy_value("durationSeconds", 7200),
                "maxQuestionsPerObjective": policy_value("maxQuestionsPerObjective", 40),
                "voiceEnabled": policy_value("voiceEnabled", os.getenv("INTERVIEW_VOICE_ENABLED", "true").lower() == "true"),
                "simliAvatarEnabled": policy_value("simliAvatarEnabled", bool(os.getenv("SIMLI_FACE_ID", "").strip())),
                "dailyQuota": policy_value("dailyQuota", 0),
            },
        },
        "openRouterConfigured": bool(credential("openRouterKey", os.getenv("OPENROUTER_API_KEY", ""))),
        "simliConfigured": bool(credential("simliKey", os.getenv("SIMLI_API_KEY", ""))),
        "embeddingDimension": matching.STAGE3_EMBEDDING_DIM,
        "embeddingLoaded": model_loader.loaded(embedding, revision),
        "evidenceReady": bool(credential("openRouterKey", os.getenv("OPENROUTER_API_KEY", ""))),
        "skillGapParameters": [
            {"key": "identity_threshold", "value": skill_gap.thresholds.identity_threshold},
            {"key": "floor_threshold", "value": skill_gap.thresholds.floor_threshold},
            {"key": "recency_years_threshold", "value": skill_gap.recency_years_threshold},
        ],
    }


router.add_api_route("/defaults", _configuration, methods=["GET"])
router.add_api_route("/status", _configuration, methods=["GET"])
