import os
import sys
import json
import time
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Type, TypeVar, Union
from pydantic import BaseModel
import openai

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

T = TypeVar('T', bound=BaseModel)


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, schema: Type[T]) -> T:
        """Execute LLM request and return structured output according to the schema."""
        pass


class OpenRouterClient(LLMClient):
    """
    OpenRouter Client sử dụng định dạng JSON Object kết hợp tắt Reasoning (thinking)
    để đạt tốc độ phản hồi tức thì (1-3s) và độ ổn định cao nhất trên Qwen và các model khác.
    """
    def __init__(self, api_key: str = None, model: str = "qwen/qwen3.7-flash"):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            self.api_key = "dummy_key"
            
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            timeout=60.0,
            max_retries=1
        )
        self.model = model

    def complete(self, prompt: str, schema: Type[T]) -> T:
        schema_json = schema.model_json_schema()
        
        system_prompt = (
            "You are a helpful assistant designed to output strictly in JSON format. "
            "Do not include any explanations, thinking process, markdown formatting, or text outside the JSON object. "
            f"Your output must perfectly validate against this JSON schema:\n{json.dumps(schema_json)}"
        )
        
        print(f"    [LLM] Đang gọi {self.model} ({schema.__name__})... ", end="", flush=True)
        
        extra_body = {
            "reasoning": {
                "effort": "none"
            }
        }
        
        max_attempts = 4
        last_exception = None
        response = None
        for attempt in range(max_attempts):
            try:
                create_kwargs = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "seed": 42,
                }
                if attempt == 0:
                    create_kwargs["extra_body"] = extra_body
                
                response = self.client.chat.completions.create(**create_kwargs)
                print("Xong!")
                break
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    wait_time = 2 ** (attempt + 1)
                    print(f"Thử lại sau {wait_time}s ({type(e).__name__})... ", end="", flush=True)
                    time.sleep(wait_time)
                else:
                    raise last_exception
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
            
        if content.endswith("```"):
            content = content[:-3]
            
        content = content.strip()
        
        try:
            data = json.loads(content)
            return schema.model_validate(data)
        except Exception as e:
            raise ValueError(f"LLM did not return a valid JSON matching the schema. Error: {str(e)}\nContent: {content}")


class DSPyLLMClient(LLMClient):
    """
    Production & Research LLM Client powered by Declarative DSPy Modules (Khattab et al., 2023).
    Executes compiled DSPy Signatures (`JobBlockExtractionSignature`, `SpanMappingSignature`,
    `JDRequirementSignature`, `SpanRichnessSignature`) while preserving the `LLMClient` interface
    for 100% compatibility with all existing services, baselines, and tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        compiled_dir: Optional[Union[str, Path]] = None,
        fallback_client: Optional[LLMClient] = None,
    ) -> None:
        import dspy
        from skill_gap.dspy_modules.modules import (
            DSPyJobBlockExtractorModule,
            DSPySpanMapperModule,
            DSPyJDRequirementParserModule,
            DSPySpanRichnessAnalyzerModule,
        )

        openrouter_key = api_key or os.environ.get("OPENROUTER_API_KEY")

        if openrouter_key:
            self.api_key = openrouter_key
            self.base_url = base_url or "https://openrouter.ai/api/v1"
            self.model = model or os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.7-flash")
            dspy_model_name = (
                self.model if self.model.startswith("openrouter/") else f"openrouter/{self.model}"
            )
        else:
            self.api_key = None
            self.base_url = base_url
            self.model = model or "qwen/qwen3.7-flash"
            dspy_model_name = f"openrouter/{self.model}"

        self.job_extractor_module = DSPyJobBlockExtractorModule()
        self.span_mapper_module = DSPySpanMapperModule()
        self.jd_parser_module = DSPyJDRequirementParserModule()
        self.span_richness_module = DSPySpanRichnessAnalyzerModule()

        comp_dir = (
            Path(compiled_dir)
            if compiled_dir
            else (Path(__file__).resolve().parent.parent / "compiled_modules")
        )
        self.compiled_dir = comp_dir
        self._load_compiled_artifacts(comp_dir)

        self.dspy_lm: Optional[dspy.LM] = None
        if self.api_key:
            lm_kwargs = {
                "api_key": self.api_key,
                "temperature": 0.0,
                "cache": False,
                "timeout": 60,
                "num_retries": 3,
                "extra_body": {"reasoning": {"effort": "none"}},
            }
            if self.base_url:
                lm_kwargs["api_base"] = self.base_url
            self.dspy_lm = dspy.LM(dspy_model_name, **lm_kwargs)

        self.fallback_client = fallback_client or (
            OpenRouterClient(api_key=self.api_key, model=self.model) if self.api_key else None
        )

    def _load_compiled_artifacts(self, comp_dir: Path) -> None:
        mapping = {
            "job_extractor.json": self.job_extractor_module,
            "span_mapper.json": self.span_mapper_module,
            "jd_parser.json": self.jd_parser_module,
            "span_richness.json": self.span_richness_module,
        }
        for filename, module in mapping.items():
            fpath = comp_dir / filename
            if fpath.exists():
                try:
                    module.load(str(fpath))
                except Exception:
                    pass

    @property
    def is_compiled(self) -> bool:
        try:
            state = self.job_extractor_module.dump_state()
            demos = state.get("extract.predict", {}).get("demos", [])
            return len(demos) > 0
        except Exception:
            return False

    def complete(self, prompt: str, schema: Type[T]) -> T:
        import dspy

        if self.dspy_lm is None:
            if self.fallback_client is not None:
                return self.fallback_client.complete(prompt, schema)
            raise RuntimeError("Missing API key for DSPyLLMClient.")

        schema_name = schema.__name__
        try:
            with dspy.context(lm=self.dspy_lm):
                if schema_name == "JobBlockExtraction":
                    cv_text = prompt.split("CV Text:", 1)[-1].strip() if "CV Text:" in prompt else prompt
                    pred = self.job_extractor_module(cv_text=cv_text)
                    return schema.model_validate({"job_blocks": pred.job_blocks})

                if schema_name == "SpanMappingExtraction":
                    jobs_ctx = prompt
                    spans_ctx = prompt
                    if "Job Blocks:" in prompt and "Evidence Spans to map:" in prompt:
                        part1 = prompt.split("Job Blocks:", 1)[1]
                        jobs_ctx, rest = part1.split("Evidence Spans to map:", 1)
                        spans_ctx = rest.split("For each evidence span", 1)[0]
                    pred = self.span_mapper_module(
                        jobs_context=jobs_ctx.strip(),
                        spans_context=spans_ctx.strip(),
                    )
                    return schema.model_validate({"span_mappings": pred.span_mappings})

                if schema_name == "JDParserOutput":
                    jd_txt = prompt
                    skills_ctx = prompt
                    if "JD Text:" in prompt and "Skills to analyze:" in prompt:
                        part1 = prompt.split("JD Text:", 1)[1]
                        jd_txt, rest = part1.split("Skills to analyze:", 1)
                        skills_ctx = rest.split("Return the required proficiency", 1)[0]
                    pred = self.jd_parser_module(
                        jd_text=jd_txt.strip(),
                        skills_context=skills_ctx.strip(),
                    )
                    return schema.model_validate({"requirements": pred.requirements})

                if schema_name == "SpanAnalysisList":
                    m = re.search(r'skill\s+"([^"]+)"', prompt)
                    skill_id = m.group(1) if m else "unknown_skill"
                    spans_txt = prompt.split("Spans:", 1)[-1].strip() if "Spans:" in prompt else prompt
                    pred = self.span_richness_module(
                        skill_id=skill_id,
                        spans_text=spans_txt,
                    )
                    return schema.model_validate({"analyses": pred.analyses})
        except Exception:
            if self.fallback_client is not None:
                return self.fallback_client.complete(prompt, schema)
            raise

        if self.fallback_client is not None:
            return self.fallback_client.complete(prompt, schema)
        raise ValueError(f"Unsupported schema '{schema_name}' without fallback client.")
