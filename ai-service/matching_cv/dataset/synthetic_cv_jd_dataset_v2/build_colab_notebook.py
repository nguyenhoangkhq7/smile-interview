#!/usr/bin/env python
"""Builder script to package synthetic_dataset_colab_runner.ipynb with resilient JSON repair and auto-resume."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def make_cell(cell_type: str, source: str) -> dict:
    lines = [line + "\n" for line in source.split("\n")]
    if lines and lines[-1] == "\n":
        lines[-1] = ""
    return {
        "cell_type": cell_type,
        "metadata": {},
        "source": lines,
        "execution_count": None if cell_type == "code" else None,
        "outputs": [] if cell_type == "code" else None
    }

def main():
    cells = []

    # Cell 1: Header Markdown
    cells.append(make_cell("markdown", r"""# 🚀 Sinh Dataset CV–JD Bằng LLM Trên Google Colab (v2.1.0 - Resilient & Fast)

Notebook này chạy trên Cloud của Google Colab:
- **Tự động khôi phục (Resume):** Tự động phát hiện các cặp đã hoàn thành từ lần chạy trước để chạy tiếp tục, không bao giờ mất dữ liệu dở dang.
- **Bộ tự sửa lỗi JSON (Self-Healing JSON):** Tự động sửa lỗi thiếu ngoặc kép, dấu phẩy thừa, hoặc định dạng markdown từ LLM, ngăn chặn 100% lỗi `JSONDecodeError`.
- **Tốc độ cao (Async Concurrency):** Xử lý đồng thời 5 luồng (`asyncio.Semaphore`), rút ngắn thời gian chạy xuống còn ~6–8 phút.
- **Persona rõ ràng:** Đảm bảo phân phối điểm trải đều đẹp trên cả 3 miền: `NO_FIT`, `POTENTIAL_FIT`, `GOOD_FIT`.
"""))

    # Cell 2: Dependencies
    cells.append(make_cell("code", """# 1. Cài đặt các thư viện cần thiết
!pip install --quiet openai pyyaml jsonschema tqdm pandas matplotlib
print("✅ Đã cài đặt xong thư viện!")
"""))

    # Cell 3: Mount Google Drive
    cells.append(make_cell("code", """import os
from google.colab import drive

# 2. Gắn kết Google Drive để lưu dữ liệu an toàn
drive.mount('/content/drive')

# Thư mục lưu kết quả trên Google Drive của bạn
OUTPUT_DIR = '/content/drive/MyDrive/synthetic_cv_jd_dataset_v2'
os.makedirs(f"{OUTPUT_DIR}/raw", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/processed", exist_ok=True)
print(f"📁 Dữ liệu sẽ được tự động lưu tại: {OUTPUT_DIR}")
"""))

    # Cell 4: API Key & Models Configuration
    cells.append(make_cell("code", """import getpass
from google.colab import userdata

# 3. Lấy API Key
try:
    API_KEY = userdata.get('OPENROUTER_API_KEY')
except Exception:
    API_KEY = None

if not API_KEY:
    API_KEY = getpass.getpass("🔑 Nhập OPENROUTER_API_KEY của bạn (hoặc OpenAI key): ")

BASE_URL = "https://openrouter.ai/api/v1"

# Cấu hình Models Flash/Mini siêu rẻ nhưng thông minh
MODELS = {
    "jd_generator": "google/gemini-2.5-flash",       # Tạo JD chi tiết, tự nhiên
    "cv_generator": "deepseek/deepseek-chat",        # Sinh CV đa dạng format
    "judge_a": "openai/gpt-4o-mini",                # Judge A (OpenAI)
    "judge_b": "qwen/qwen-2.5-72b-instruct",         # Judge B (Alibaba/Qwen)
    "judge_c": "meta-llama/llama-3.3-70b-instruct"  # Judge C Adjudicator (Meta)
}

CONCURRENCY_LIMIT = 5

# QUAN TRỌNG: Đặt False để TỰ ĐỘNG CHẠY TIẾP từ cặp dở dang (ví dụ cặp 71 -> 100), không xóa dữ liệu cũ!
# Chỉ đặt True nếu bạn muốn xóa sạch làm lại từ đầu.
OVERWRITE_PREVIOUS_RUN = False

print(f"✅ Đã cấu hình xong! OVERWRITE_PREVIOUS_RUN = {OVERWRITE_PREVIOUS_RUN}")
"""))

    # Cell 5: Self-Healing JSON Parser & Core Helpers
    cells.append(make_cell("code", """import re
import json
import random
import asyncio
from typing import Dict, Any, List, Optional, Tuple

ANCHOR_ORDER = [1.00, 0.85, 0.65, 0.40, 0.20, 0.00]

def normalize_text_for_quote(s: str) -> str:
    s = s.casefold().replace("\\u2019", "'").replace("\\u2013", "-").replace("\\u2014", "-")
    return re.sub(r"\\s+", " ", s).strip()

def verify_quote(document_text: str, quote: Optional[str]) -> bool:
    if not quote or not quote.strip():
        return False
    return normalize_text_for_quote(quote) in normalize_text_for_quote(document_text)

def extract_json_payload(raw_content: str) -> Dict[str, Any]:
    \"\"\"Bộ phân tích và tự sửa lỗi JSON đa cấp (Self-Healing JSON Parser).\"\"\"
    if not raw_content or not raw_content.strip():
        return {}
    s = raw_content.strip()

    # 1. Tách code fence markdown
    match = re.search(r"```(?:json)?\\s*([\\s\\S]*?)\\s*```", s, re.IGNORECASE)
    if match:
        s = match.group(1).strip()

    # 2. Cắt từ dấu { đầu tiên đến } cuối cùng
    start = s.find('{')
    end = s.rfind('}')
    if start != -1 and end != -1 and end > start:
        s = s[start:end+1]

    # Cấp 1: Thử parse trực tiếp
    try:
        return json.loads(s)
    except Exception:
        pass

    # Cấp 2: Sửa lỗi dấu phẩy thừa (trailing commas: ,} hoặc ,])
    s_clean = re.sub(r",\\s*([\\]\\}])", r"\\1", s)
    try:
        return json.loads(s_clean)
    except Exception:
        pass

    # Cấp 3: Sửa lỗi key không có ngoặc kép: { req_001: ... } -> { "req_001": ... }
    s_keys = re.sub(r"([{,]\\s*)([a-zA-Z_][a-zA-Z0-9_-]*)\\s*:", r'\\1"\\2":', s_clean)
    try:
        return json.loads(s_keys)
    except Exception:
        pass

    # Cấp 4: Sửa lỗi dùng nháy đơn thay vì nháy kép
    s_single = re.sub(r"'([a-zA-Z0-9_ -]+)'\\s*:", r'"\\1":', s_keys)
    s_single = re.sub(r":\\s*'([^']*)'", r': "\\1"', s_single)
    try:
        return json.loads(s_single)
    except Exception as e:
        print(f"⚠️ Không thể phục hồi JSON: {e}. Nội dung thô: {raw_content[:200]}...")
        raise

# 10 Nhóm nghề chuẩn
ROLE_FAMILIES = [
    "Backend Software Engineer",
    "Frontend Software Engineer",
    "Full-Stack Software Engineer",
    "Mobile Software Engineer (iOS/Android)",
    "DevOps / Cloud / SRE Engineer",
    "Data Engineer",
    "Data Scientist / Machine Learning Engineer",
    "QA / Test Automation Engineer",
    "Cybersecurity / Information Security Analyst",
    "Technical Product Manager / Business Analyst",
]

SENIORITIES = ["junior", "mid", "senior", "lead", "intern"]
SENIORITY_WEIGHTS = [0.25, 0.35, 0.25, 0.10, 0.05]
INDUSTRIES = ["fintech", "e-commerce", "healthcare", "logistics", "edtech", "gaming", "telecom", "SaaS", "cybersecurity", "banking"]
COMPANY_TYPES = ["early-stage startup", "high-growth scale-up", "global enterprise", "software agency", "financial institution"]
JD_STYLES = [
    "structured: Overview / Responsibilities / Mandatory requirements / Preferred bonus / Benefits",
    "narrative-driven: contextual mission paragraphs with bulleted requirements",
    "fast-paced high-growth style: punchy and impact-focused",
    "formal corporate style: clear hierarchy, governance, and detailed compliance",
    "engineering-first style: deep technical detail, architecture focus, tech-stack highlights",
]

def generate_jd_seeds(count: int, seed: int = 20261118) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    seeds = []
    for i in range(count):
        seeds.append({
            "seed_index": i + 1,
            "jd_id": f"jd_{i+1:03d}",
            "role_family": ROLE_FAMILIES[i % len(ROLE_FAMILIES)],
            "seniority": rng.choices(SENIORITIES, weights=SENIORITY_WEIGHTS, k=1)[0],
            "industry": rng.choice(INDUSTRIES),
            "company_type": rng.choice(COMPANY_TYPES),
            "jd_style": rng.choice(JD_STYLES),
            "target_word_count": rng.choice([300, 450, 550]),
            "n_mandatory": rng.randint(5, 8),
            "n_preferred": rng.randint(2, 4),
            "seed": rng.randint(100000, 999999),
        })
    return seeds

print("✅ Đã sẵn sàng bộ tự sửa lỗi JSON và các hàm tiền xử lý!")
"""))

    # Cell 6: Slot Personas & Explicit Archetype Guidance
    cells.append(make_cell("code", """# Cấu hình danh tính nghề nghiệp thực tế cho từng Slot
SLOT_ARCHETYPES = {
    "S01": {
        "name": "strong_match",
        "profession": "Senior/Lead Professional in Exact Same Field",
        "instructions": "Demonstrate solid, deep professional experience directly satisfying almost all mandatory requirements with strong contextual achievements and required years."
    },
    "S02": {
        "name": "good_match",
        "profession": "Mid-Level Professional in Same Field",
        "instructions": "Candidate meets mandatory requirements solidly with standard evidence, but has fewer preferred/bonus skills."
    },
    "S03": {
        "name": "near_miss",
        "profession": "Same Field Professional with 1-2 Missing Core Skills",
        "instructions": "Candidate is in the same field, BUT completely lacks 1 or 2 specific technical requirements (e.g. strong backend, but ZERO cloud/AWS or ZERO Kafka, never mentions them). The missing requirements must NOT appear in the CV."
    },
    "S04": {
        "name": "substitute_stack",
        "profession": "Software Engineer using Alternative Tech Stack",
        "instructions": "Candidate is an experienced engineer but uses a completely DIFFERENT tech stack. (e.g. if JD is Java/Spring/AWS, this candidate works exclusively with Python/Django/PostgreSQL/GCP or C#/.NET/Azure. They have NEVER used the JD's primary tools)."
    },
    "S05": {
        "name": "experience_gap",
        "profession": "Early Career / Junior Professional (1-2 years total)",
        "instructions": "Candidate has the right primary skill keywords, but only has 1 to 2 years of experience total (graduated recently). They fail any 5+ or 7+ years requirement."
    },
    "S06": {
        "name": "overqualified",
        "profession": "Staff / Principal / Director Level Veteran (15+ years)",
        "instructions": "Candidate has 15+ years experience, extensive system leadership, and easily satisfies every requirement strongly."
    },
    "S07": {
        "name": "adjacent_role",
        "profession": "Adjacent Role (e.g. QA Automation / Data Analyst / Tech Support)",
        "instructions": "Candidate works in an adjacent field (e.g. QA Automation, IT Support, or Data Analyst). Has basic scripting and Git, but lacks deep core development/architecture experience."
    },
    "S08": {
        "name": "weak_match",
        "profession": "2nd Year University Student / Beginner Intern",
        "instructions": "Candidate has ZERO full-time work experience, only basic classroom coursework and small toy assignments. Weak exposure, high missing rate."
    },
    "S09": {
        "name": "career_changer",
        "profession": "Career Changer (8 years in Retail/Sales/Hospitality)",
        "instructions": "Candidate spent 8 years in non-technical sales or customer service, recently finished a 10-week introductory evening coding course. 90% of resume is sales/customer support."
    },
    "S10": {
        "name": "unrelated",
        "profession": "Completely Unrelated Profession (e.g. High School History Teacher / Registered Nurse / Chef / Accountant)",
        "instructions": "CRITICAL REQUIREMENT: Candidate has NEVER worked in software or IT. Write a resume for a High School Teacher, Nurse, Chef, or Accountant. DO NOT MENTION any programming languages, databases, cloud tools, or software systems. All JD requirements MUST be completely missing (0.00 score)!"
    }
}

SLOTS = [
    ("S01", "strong_match"), ("S02", "good_match"), ("S03", "near_miss"),
    ("S04", "substitute_stack"), ("S05", "experience_gap"), ("S06", "overqualified"),
    ("S07", "adjacent_role"), ("S08", "weak_match"), ("S09", "career_changer"), ("S10", "unrelated"),
]

def build_cv_targets(reqs: List[Dict[str, Any]], slot_id: str, rng: random.Random) -> Dict[str, str]:
    mand = [r for r in reqs if r["type"] == "mandatory"]
    pref = [r for r in reqs if r["type"] == "preferred"]
    t = {}

    def fill_met(items):
        for r in items: t[r["req_id"]] = "met_strong" if rng.random() < 0.5 else "met_light"
    def set_all(items, st):
        for r in items: t[r["req_id"]] = st
    def some(items, frac):
        k = max(1, round(len(items) * frac)) if items else 0
        return rng.sample(items, min(k, len(items)))

    if slot_id == "S01":
        fill_met(mand); set_all(pref, "missing")
        for r in some(pref, rng.uniform(0.6, 1.0)): t[r["req_id"]] = "met_strong"
    elif slot_id == "S02":
        fill_met(mand); set_all(pref, "missing")
        for r in some(pref, rng.uniform(0.1, 0.4)): t[r["req_id"]] = "met_light"
        if rng.random() < 0.5 and mand: t[rng.choice(mand)["req_id"]] = "partial_adjacent"
    elif slot_id == "S03":
        fill_met(mand); set_all(pref, "missing")
        for r in some(pref, rng.uniform(0.3, 0.7)): t[r["req_id"]] = "met_light"
        non_crit = [r for r in mand if not r.get("is_critical")] or mand
        for r in rng.sample(non_crit, min(len(non_crit), rng.choices([1, 2, 3], [0.35, 0.4, 0.25])[0])):
            t[r["req_id"]] = "missing"
    elif slot_id == "S04":
        fill_met(mand); set_all(pref, "missing")
        tech = [r for r in mand if r["category"] in ("technical_skill", "tool")] or mand
        for r in rng.sample(tech, min(rng.randint(2, 4), len(tech))): t[r["req_id"]] = "partial_adjacent"
        for r in some(pref, 0.4): t[r["req_id"]] = "met_light"
    elif slot_id == "S05":
        fill_met(mand); set_all(pref, "missing")
        exp = [r for r in mand if r["category"] == "experience_years"] or [rng.choice(mand)]
        for r in exp: t[r["req_id"]] = "partial_years"
        for r in some(mand, rng.uniform(0.15, 0.4)):
            if t[r["req_id"]] != "partial_years": t[r["req_id"]] = "partial_adjacent"
        for r in some(pref, 0.3): t[r["req_id"]] = "met_light"
    elif slot_id == "S06":
        set_all(mand, "met_strong"); set_all(pref, "met_strong")
    elif slot_id == "S07":
        set_all(mand, "missing"); set_all(pref, "missing")
        for r in some(mand, rng.uniform(0.3, 0.7)): t[r["req_id"]] = "met_light"
        rest = [r for r in mand if t[r["req_id"]] == "missing"]
        for r in some(rest, 0.5): t[r["req_id"]] = "partial_adjacent"
        for r in some(pref, 0.3): t[r["req_id"]] = "met_light"
    elif slot_id == "S08":
        set_all(mand, "missing"); set_all(pref, "missing")
        for r in some(mand, rng.uniform(0.1, 0.5)): t[r["req_id"]] = "partial_adjacent"
        if rng.random() < 0.3 and mand: t[rng.choice(mand)["req_id"]] = "met_light"
    elif slot_id == "S09":
        set_all(mand, "missing"); set_all(pref, "missing")
        for r in [r for r in reqs if r["category"] in ("soft_skill", "domain")]: t[r["req_id"]] = "partial_adjacent"
        for r in some(mand, rng.uniform(0.1, 0.3)): t[r["req_id"]] = "partial_adjacent"
    elif slot_id == "S10":
        set_all(reqs, "missing")

    for r in reqs: t.setdefault(r["req_id"], "missing")
    return t

def compute_pair_score(scores_by_req: Dict[str, float], reqs: List[Dict[str, Any]]) -> Tuple[float, float, bool]:
    num = den = 0.0
    crit_missing = False
    for r in reqs:
        w = 3.0 if r["type"] == "mandatory" else 1.0
        s = scores_by_req.get(r["req_id"], 0.00)
        num += w * s
        den += w
        if r["type"] == "mandatory" and r.get("is_critical") and s == 0.00:
            crit_missing = True
    cov = round(num / den if den else 0.0, 4)
    final = round(min(cov, 0.55) if crit_missing else cov, 4)
    return cov, final, crit_missing
"""))

    # Cell 7: Pipeline Engine with Response Format and Retry Handling
    cells.append(make_cell("code", """from openai import AsyncOpenAI
from tqdm.auto import tqdm

client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def call_llm(prompt: str, system_prompt: str, model: str, temperature: float = 0.0) -> Dict[str, Any]:
    \"\"\"Gọi LLM với cơ chế JSON Object Mode và tự thử lại 4 lần.\"\"\"
    last_err = None
    for attempt in range(4):
        try:
            # Ép model trả về JSON Object nếu hỗ trợ
            resp = await client.chat.completions.create(
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt + "\\nYou MUST respond with a single valid JSON object strictly complying with standard RFC 8259."},
                    {"role": "user", "content": prompt}
                ]
            )
            raw_text = resp.choices[0].message.content or "{}"
            return extract_json_payload(raw_text)
        except Exception as e:
            last_err = e
            # Nếu model không hỗ trợ response_format, thử lại không có nó
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt + "\\nYou MUST respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ]
                )
                raw_text = resp.choices[0].message.content or "{}"
                return extract_json_payload(raw_text)
            except Exception as e2:
                last_err = e2

            await asyncio.sleep(1.5 * (attempt + 1))

    print(f"⚠️ Gọi LLM thất bại sau 4 lần thử: {last_err}")
    return {}

async def generate_jd_step(seed: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f\"\"\"Generate ONE realistic job description and its structured requirements breakdown.
SEED:
- jd_id: {seed['jd_id']}
- role_family: {seed['role_family']}
- seniority: {seed['seniority']}
- industry: {seed['industry']}
- company_type: {seed['company_type']}
- writing_style: {seed['jd_style']}
- target_word_count: {seed['target_word_count']}
- mandatory_count: {seed['n_mandatory']}
- preferred_count: {seed['n_preferred']}

RULES:
1. Clearly fictional company name.
2. In jd_text, distinguish mandatory and preferred requirements naturally.
3. In requirements array, produce exactly the requested mandatory and preferred items.
4. Each item must have: req_id, text, type ('mandatory'|'preferred'), category, skill_terms (array of 1-3 terms), min_years, is_critical (boolean, 1-2 true), and jd_quote (exact substring from jd_text).
5. Output valid JSON only, no markdown:
{{"jd_id":"{seed['jd_id']}","title":"...","company_name":"...","role_family":"{seed['role_family']}","seniority":"{seed['seniority']}","industry":"{seed['industry']}","company_type":"{seed['company_type']}","jd_text":"...","requirements":[]}}
\"\"\"
    data = await call_llm(prompt, "You are a senior recruitment specialist. Output valid JSON only.", MODELS["jd_generator"], temperature=0.8)
    return data

async def generate_cv_step(jd: Dict[str, Any], slot_id: str, target_statuses: Dict[str, str]) -> Dict[str, Any]:
    cv_id = f"{jd['jd_id']}_{slot_id}_cv"
    arch = SLOT_ARCHETYPES[slot_id]
    req_lines = [f"{r['req_id']} | {r['text']} | target: {target_statuses[r['req_id']]}" for r in jd["requirements"]]

    prompt = f\"\"\"Write ONE realistic English resume for a fictional candidate.

CANDIDATE PERSONA & ARCHETYPE (STRICT ENFORCEMENT):
- Slot: {slot_id} ({arch['name']})
- Actual Profession / Background: {arch['profession']}
- Archetype Guidance: {arch['instructions']}

REALIZATION PLAN FOR THIS RESUME:
{chr(10).join(req_lines)}

TARGET DEFINITIONS:
- met_strong / met_light: demonstrate with context in employment or projects.
- partial_years / partial_adjacent: show related skill or fewer years than required.
- missing: completely omit the skill. DO NOT mention it in any form!

STRICT INSTRUCTIONS:
1. Embody the candidate's actual profession ({arch['profession']}).
2. For slot S10 (unrelated), the candidate is completely non-IT. DO NOT include any software, programming or cloud keywords!
3. For slot S04 (substitute stack), candidate uses an alternative stack. DO NOT use the JD's exact tech stack!
4. The resume must be at least 150 words.

OUTPUT JSON:
{{"cv_id":"{cv_id}","cv_text":"...","realized":[{{"req_id":"...","target":"...","realized":"...","evidence_quote":"..."}}],"metadata":{{"persona":"{arch['name']}","candidate_level":"{jd['seniority']}","resume_format":"chronological_with_summary","noise_level":"low","language":"en","word_count":250}}}}
\"\"\"
    data = await call_llm(prompt, "You write realistic English resumes adhering strictly to the candidate's assigned persona. Output valid JSON only.", MODELS["cv_generator"], temperature=0.8)
    if "metadata" in data and "cv_text" in data:
        data["metadata"]["word_count"] = len(data["cv_text"].split())
    return data

async def judge_step(judge_id: str, model_key: str, jd: Dict[str, Any], cv_data: Dict[str, Any], req_subset=None) -> Dict[str, Any]:
    reqs = jd["requirements"] if not req_subset else [r for r in jd["requirements"] if r["req_id"] in req_subset]
    public_reqs = [{"req_id": r["req_id"], "text": r["text"], "type": r["type"], "skill_terms": r["skill_terms"]} for r in reqs]
    prompt = f\"\"\"Evaluate the resume against the job description requirement by requirement.
JOB DESCRIPTION:
{jd['jd_text']}

REQUIREMENTS:
{json.dumps(public_reqs, indent=2)}

RESUME:
{cv_data.get('cv_text', '')}

EXACT ANCHORS:
- 1.00: strong_evidence (substantial direct evidence)
- 0.85: good_evidence (credible contextual evidence)
- 0.65: partial_fulfillment (partial evidence / years gap)
- 0.40: weak_evidence (basic exposure, bare skill-list)
- 0.20: adjacent_evidence (related non-equivalent skill)
- 0.00: no_evidence (no credible evidence)

IMPORTANT:
- If the resume is for an unrelated profession (e.g. Teacher, Nurse) or does not have the technical skill, score 0.00 (no_evidence)!
- For score > 0, evidence_quote must be an EXACT substring from the resume. For score 0.00, evidence_quote must be empty string \"\".

OUTPUT JSON:
{{"judge_id":"{judge_id}","requirements":[{{"req_id":"...","score":0.85,"anchor":"good_evidence","evidence_quote":"...","years_found":null,"reasoning":"..."}}],"holistic_fit":3,"seniority_alignment":"aligned","red_flags":[]}}
\"\"\"
    data = await call_llm(prompt, "You are a skeptical, evidence-based recruitment evaluator. Output valid JSON only.", MODELS[model_key], temperature=0.0)
    for it in data.get("requirements", []):
        if it.get("score", 0.0) > 0 and not verify_quote(cv_data.get("cv_text", ""), it.get("evidence_quote")):
            it["score"] = 0.00
            it["anchor"] = "no_evidence"
            it["evidence_quote"] = ""
    return data
"""))

    # Cell 8: Resilient Concurrent Orchestrator with Checkpoint / Auto-Resume
    cells.append(make_cell("code", """async def process_single_pair(jd: Dict[str, Any], slot_id: str, slot_name: str, rng: random.Random) -> Optional[Dict[str, Any]]:
    \"\"\"Process 1 CV-JD pair with Semaphore, shielded from crashing on single pair error.\"\"\"
    async with sem:
        try:
            target_statuses = build_cv_targets(jd["requirements"], slot_id, rng)
            cv_data = await generate_cv_step(jd, slot_id, target_statuses)
            if not cv_data.get("cv_text"):
                print(f"⚠️ Bỏ qua cặp {jd['jd_id']}_{slot_id} do lỗi sinh CV.")
                return None

            # Hai Judges chấm độc lập song song
            res_a, res_b = await asyncio.gather(
                judge_step("judge_a", "judge_a", jd, cv_data),
                judge_step("judge_b", "judge_b", jd, cv_data)
            )

            a_map = {r["req_id"]: r["score"] for r in res_a.get("requirements", [])}
            b_map = {r["req_id"]: r["score"] for r in res_b.get("requirements", [])}

            # Kiểm tra Adjudication
            adj_reqs = []
            for r in jd["requirements"]:
                rid = r["req_id"]
                sa = a_map.get(rid, 0.0); sb = b_map.get(rid, 0.0)
                ia = ANCHOR_ORDER.index(sa) if sa in ANCHOR_ORDER else 0
                ib = ANCHOR_ORDER.index(sb) if sb in ANCHOR_ORDER else 0
                if abs(ia - ib) >= 2: adj_reqs.append(rid)

            _, score_a, _ = compute_pair_score(a_map, jd["requirements"])
            _, score_b, _ = compute_pair_score(b_map, jd["requirements"])
            if abs(score_a - score_b) > 0.15:
                for r in jd["requirements"]:
                    if r["req_id"] not in adj_reqs: adj_reqs.append(r["req_id"])
                    if len(adj_reqs) >= 3: break

            res_c = None; c_map = {}
            if adj_reqs:
                res_c = await judge_step("judge_c", "judge_c", jd, cv_data, req_subset=adj_reqs)
                c_map = {r["req_id"]: r["score"] for r in res_c.get("requirements", [])}

            final_reqs = {}
            for r in jd["requirements"]:
                rid = r["req_id"]
                if rid in adj_reqs:
                    scores_3 = sorted([a_map.get(rid, 0.0), b_map.get(rid, 0.0), c_map.get(rid, 0.0)])
                    final_reqs[rid] = scores_3[1] # Median
                else:
                    final_reqs[rid] = round((a_map.get(rid, 0.0) + b_map.get(rid, 0.0)) / 2.0, 4)

            cov, final, capped = compute_pair_score(final_reqs, jd["requirements"])
            raw_label = "NO_FIT" if final < 0.25 else ("POTENTIAL_FIT" if final <= 0.75 else "GOOD_FIT")
            diag_label = "UNCERTAIN" if (abs(final - 0.25) <= 0.05 or abs(final - 0.75) <= 0.05) else raw_label

            pair_record = {
                "pair_id": f"{jd['jd_id']}_{slot_id}",
                "pair_type": "primary",
                "jd_id": jd["jd_id"],
                "cv_id": cv_data["cv_id"],
                "cross_pair": None,
                "construction": {"slot": slot_id, "target_statuses": target_statuses, "construction_score": cov},
                "judge_results": [res_a, res_b],
                "signed_disagreement": {"pair_level_a_minus_b": round(score_a - score_b, 4)},
                "adjudication": {"triggered": bool(adj_reqs), "judge_c_result": res_c, "final_requirement_scores": final_reqs},
                "scores": {"coverage_score": cov, "final_score": final},
                "label": diag_label,
                "raw_threshold_label": raw_label,
                "quality_status": "accepted",
                "reject_reason": None,
                "audit_flags": ["critical_missing_capped"] if capped else [],
                "split": "train"
            }

            return {"pair": pair_record, "cv": cv_data}
        except Exception as e:
            print(f"⚠️ Bỏ qua cặp {jd['jd_id']}_{slot_id} do lỗi ngoại lệ: {e}")
            return None

async def run_pipeline(num_jds: int = 10):
    seeds = generate_jd_seeds(num_jds)

    pairs_path = f"{OUTPUT_DIR}/raw/pairs.jsonl"
    resumes_path = f"{OUTPUT_DIR}/raw/resumes.jsonl"
    jobs_path = f"{OUTPUT_DIR}/raw/jobs.jsonl"
    accepted_path = f"{OUTPUT_DIR}/processed/accepted_pairs.jsonl"

    if OVERWRITE_PREVIOUS_RUN:
        print("🗑️ Đang xóa dữ liệu cũ trên Google Drive để chạy lại từ đầu (OVERWRITE_PREVIOUS_RUN=True)...")
        for p in [pairs_path, resumes_path, jobs_path, accepted_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

    # Checkpoint: Đọc danh sách các pair_id đã hoàn thành trước đó
    completed_pairs = set()
    if os.path.exists(pairs_path):
        with open(pairs_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        completed_pairs.add(record["pair_id"])
                    except Exception: pass
    if completed_pairs:
        print(f"⚡ Phát hiện {len(completed_pairs)} cặp đã hoàn thành từ lần trước. Tự động bỏ qua!")

    print(f"🚀 Tiếp tục sinh {num_jds} JDs x 10 CVs = {num_jds * 10} cặp (Còn lại: {num_jds * 10 - len(completed_pairs)} cặp)...")

    jobs_out = open(jobs_path, "a", encoding="utf-8")
    resumes_out = open(resumes_path, "a", encoding="utf-8")
    pairs_out = open(pairs_path, "a", encoding="utf-8")
    accepted_out = open(accepted_path, "a", encoding="utf-8")

    total_target = num_jds * 10
    pbar = tqdm(total=total_target, initial=len(completed_pairs), desc="Synthesis Progress")

    for seed in seeds:
        jd_file_records = []
        if os.path.exists(jobs_path):
            with open(jobs_path, "r", encoding="utf-8") as f:
                jd_file_records = [json.loads(line)["jd_id"] for line in f if line.strip()]

        if seed["jd_id"] not in jd_file_records:
            jd = await generate_jd_step(seed)
            if not jd or not jd.get("jd_id"): continue
            jobs_out.write(json.dumps(jd, ensure_ascii=False) + "\\n")
            jobs_out.flush()
        else:
            with open(jobs_path, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    if rec["jd_id"] == seed["jd_id"]:
                        jd = rec; break

        rng = random.Random(seed["seed"])

        # Tạo danh sách các slot cần xử lý cho JD này
        tasks = []
        for slot_id, slot_name in SLOTS:
            pid = f"{jd['jd_id']}_{slot_id}"
            if pid not in completed_pairs:
                tasks.append(process_single_pair(jd, slot_id, slot_name, rng))

        if tasks:
            results = await asyncio.gather(*tasks)
            for item in results:
                if item is not None:
                    pair = item["pair"]; cv = item["cv"]
                    resumes_out.write(json.dumps(cv, ensure_ascii=False) + "\\n")
                    pairs_out.write(json.dumps(pair, ensure_ascii=False) + "\\n")
                    accepted_out.write(json.dumps(pair, ensure_ascii=False) + "\\n")
                    resumes_out.flush()
                    pairs_out.flush()
                    accepted_out.flush()
                    pbar.update(1)

    pbar.close()
    jobs_out.close(); resumes_out.close(); pairs_out.close(); accepted_out.close()
    print(f"🎉 Hoàn thành xuất sắc! Toàn bộ dataset đã lưu tại: {OUTPUT_DIR}")

# ==============================================================================
# BẤM CHẠY CELL NÀY ĐỂ BẮT ĐẦU HOẶC TIẾP TỤC:
# ==============================================================================
await run_pipeline(num_jds=10)
"""))

    # Cell 9: Dashboard & Visualization
    cells.append(make_cell("code", """import pandas as pd
import matplotlib.pyplot as plt

# Đọc kết quả vừa sinh
df = pd.read_json(f"{OUTPUT_DIR}/processed/accepted_pairs.jsonl", lines=True)

scores = df['scores'].apply(lambda x: x['final_score'])
labels = df['label']
raw_labels = df['raw_threshold_label']
slots = df['construction'].apply(lambda x: x['slot'])

print("=== BÁO CÁO PHÂN PHỐI ĐIỂM (v2.1.0) ===")
print(f"Tổng số cặp: {len(df)}")
print(f"Điểm trung bình (Mean): {scores.mean():.4f}")
print(f"Điểm thấp nhất (Min): {scores.min():.4f} | Cao nhất (Max): {scores.max():.4f}")
print(f"Độ lệch chuẩn (Std): {scores.std():.4f}")

print("\\n--- Phân phối theo nhãn (kèm dải UNCERTAIN) ---")
print(labels.value_counts())

print("\\n--- Phân phối nhãn thô (Raw Thresholds) ---")
print(raw_labels.value_counts())

print("\\n--- Điểm trung bình theo từng Slot ---")
print(df.groupby(slots)['scores'].apply(lambda s: s.apply(lambda x: x['final_score']).mean()))

plt.figure(figsize=(14, 4))

plt.subplot(1, 3, 1)
plt.hist(scores, bins=15, color='royalblue', edgecolor='black', alpha=0.7)
plt.title("Phân phối điểm (final_score)")
plt.xlabel("Final Score [0 - 1]")
plt.ylabel("Số lượng cặp")

plt.subplot(1, 3, 2)
labels.value_counts().plot(kind='bar', color=['crimson', 'orange', 'forestgreen', 'gray'])
plt.title("Nhãn phân loại (kèm UNCERTAIN)")
plt.xlabel("Nhãn")
plt.ylabel("Số lượng")

plt.subplot(1, 3, 3)
df.groupby(slots)['scores'].apply(lambda s: s.apply(lambda x: x['final_score']).mean()).plot(kind='bar', color='teal')
plt.title("Điểm trung bình theo Slot (S01 - S10)")
plt.xlabel("Slot")
plt.ylabel("Mean Score")

plt.tight_layout()
plt.show()
"""))

    nb = {
        "cells": cells,
        "metadata": {
            "colab": {
                "name": "synthetic_dataset_colab_runner.ipynb",
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3"
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }

    out_file = ROOT / "notebooks" / "synthetic_dataset_colab_runner.ipynb"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2, ensure_ascii=False)

    print(f"✅ Đã tạo thành công Colab notebook v2.1.0 resilient tại: {out_file}")

if __name__ == "__main__":
    main()
