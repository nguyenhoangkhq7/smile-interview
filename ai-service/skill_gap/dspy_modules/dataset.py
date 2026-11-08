"""
Gold Few-Shot Demonstration & Evaluation Dataset for Module 2 (skill_gap) DSPy Teleprompters.

Design Principles:
1. Chain-of-Thought Grounding: Every `dspy.Example` includes an explicit step-by-step `reasoning` field
   so `dspy.ChainOfThought` compiles full analytical rationales into `compiled_modules/*.json`.
2. Edge-Case Coverage: Covers all critical boundary conditions from `eval_benchmark.py` and Phase 3 validation:
   - Verbatim `raw_quote` substring preservation & diverse Vietnamese/English date formats.
   - Overlapping parallel jobs (Interval Union), same-company role promotions, and fresher CVs (`job_blocks=[]`).
   - Job-specific spans vs. global `UNASSIGNED` skill lists, certifications, and coursework.
   - Hierarchical Inference Priority Rules (1: Task Complexity/Depth -> 2: Skill-specific Years -> 3: Seniority Fallback) on [1.0, 5.0].
   - Nuanced distinction between `RICH_CONTEXT`, `LIST_ONLY` (including ungrounded self-claims), and `AMBIGUOUS`.
"""

from typing import Dict, List, Tuple
import dspy
from .jd_examples import get_gold_jd_requirement_examples
from skill_gap.domain.enums import SeniorityLevel, RichnessLabel
from skill_gap.domain.models import (
    JobBlock,
    SpanMapping,
    JDRequirement,
    SpanRichness,
    UNASSIGNED_JOB_ID,
)


def get_gold_job_extraction_examples() -> List[dspy.Example]:
    """Return 5 diverse gold examples with Chain-of-Thought reasoning for JobBlockExtractionSignature."""
    return [
        # Example 1: Lead (ongoing 'Hiện tại') + Mid role in Vietnamese CV
        dspy.Example(
            cv_text=(
                "Jane Smith - DevOps Engineer\n"
                "Công ty CloudNine (03/2024 - Hiện tại) - Vị trí: DevOps Lead\n"
                "- Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.\n"
                "Công ty StartupXYZ (06/2019 - 02/2024) - Vị trí: DevOps Engineer\n"
                "- Quản lý cluster Kubernetes quy mô nhỏ, khoảng 10 services.\n"
                "- Viết Terraform để provision hạ tầng AWS."
            ),
            reasoning=(
                "1. Quét văn bản CV và xác định có 2 khối công việc thực tế tại Công ty CloudNine và Công ty StartupXYZ.\n"
                "2. Khối 1 (job_1): Chức danh 'DevOps Lead' tương ứng mức độ tự chủ cao nhất -> seniority_level='Lead'. "
                "Giữ nguyên văn raw_quote='Công ty CloudNine (03/2024 - Hiện tại) - Vị trí: DevOps Lead', "
                "raw_start_date='03/2024' -> start_date='2024-03', raw_end_date='Hiện tại' (đang làm việc) -> end_date=None.\n"
                "3. Khối 2 (job_2): Chức danh 'DevOps Engineer' thực hiện độc lập quản lý cluster và viết Terraform -> seniority_level='Mid'. "
                "Giữ nguyên văn raw_quote='Công ty StartupXYZ (06/2019 - 02/2024) - Vị trí: DevOps Engineer', "
                "raw_start_date='06/2019' -> start_date='2019-06', raw_end_date='02/2024' -> end_date='2024-02'."
            ),
            job_blocks=[
                JobBlock(
                    job_id="job_1",
                    title="DevOps Lead",
                    seniority_level=SeniorityLevel.LEAD,
                    raw_start_date="03/2024",
                    raw_end_date="Hiện tại",
                    raw_quote="Công ty CloudNine (03/2024 - Hiện tại) - Vị trí: DevOps Lead",
                    start_date="2024-03",
                    end_date=None,
                    raw_text="Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.",
                ),
                JobBlock(
                    job_id="job_2",
                    title="DevOps Engineer",
                    seniority_level=SeniorityLevel.MID,
                    raw_start_date="06/2019",
                    raw_end_date="02/2024",
                    raw_quote="Công ty StartupXYZ (06/2019 - 02/2024) - Vị trí: DevOps Engineer",
                    start_date="2019-06",
                    end_date="2024-02",
                    raw_text="Quản lý cluster Kubernetes quy mô nhỏ, khoảng 10 services. Viết Terraform để provision hạ tầng AWS.",
                ),
            ],
        ).with_inputs("cv_text"),

        # Example 2: Overlapping jobs (Full-time + Parallel Freelance) + Education/Skills exclusion
        dspy.Example(
            cv_text=(
                "NGUYỄN VĂN A - BACKEND ENGINEER\n"
                "HỌC VẤN:\n"
                "Đại học Bách Khoa (09/2017 - 06/2021) - Kỹ sư Khoa học Máy tính\n\n"
                "KINH NGHIỆM LÀM VIỆC:\n"
                "1. FinTech Corp (Jan 2022 - Dec 2023) | Senior Backend Developer\n"
                "- Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS.\n"
                "2. Global Retail Lab (06/2022 - 06/2023) | Part-time Backend Consultant\n"
                "- Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python.\n\n"
                "KỸ NĂNG KHÁC: Python, Golang, Docker, Redis, Git."
            ),
            reasoning=(
                "1. Bỏ qua mục 'HỌC VẤN' (Đại học Bách Khoa) và mục 'KỸ NĂNG KHÁC' vì không phải kinh nghiệm làm việc thực tế.\n"
                "2. Trích xuất 2 công việc có thời gian chồng lấp (FinTech Corp và Global Retail Lab) thành 2 JobBlock riêng biệt để thuật toán Interval Union xử lý ở bước sau.\n"
                "3. job_1: 'Senior Backend Developer' -> seniority_level='Senior', raw_start_date='Jan 2022' -> '2022-01', raw_end_date='Dec 2023' -> '2023-12', raw_quote nguyên văn từ CV.\n"
                "4. job_2: 'Part-time Backend Consultant' (tư vấn độc lập) -> seniority_level='Mid', raw_start_date='06/2022' -> '2022-06', raw_end_date='06/2023' -> '2023-06'."
            ),
            job_blocks=[
                JobBlock(
                    job_id="job_1",
                    title="Senior Backend Developer",
                    seniority_level=SeniorityLevel.SENIOR,
                    raw_start_date="Jan 2022",
                    raw_end_date="Dec 2023",
                    raw_quote="1. FinTech Corp (Jan 2022 - Dec 2023) | Senior Backend Developer",
                    start_date="2022-01",
                    end_date="2023-12",
                    raw_text="Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS.",
                ),
                JobBlock(
                    job_id="job_2",
                    title="Part-time Backend Consultant",
                    seniority_level=SeniorityLevel.MID,
                    raw_start_date="06/2022",
                    raw_end_date="06/2023",
                    raw_quote="2. Global Retail Lab (06/2022 - 06/2023) | Part-time Backend Consultant",
                    start_date="2022-06",
                    end_date="2023-06",
                    raw_text="Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python.",
                ),
            ],
        ).with_inputs("cv_text"),

        # Example 3: Supervised roles (Intern & Junior) with Vietnamese 'T3/2021' and year-only dates
        dspy.Example(
            cv_text=(
                "Trần Minh Hoàng - Frontend Developer\n"
                "Kinh nghiệm:\n"
                "Công ty WebStudio (Tháng 10/2021 - 2023) - Junior Frontend Developer\n"
                "- Phát triển giao diện người dùng bằng Vue.js và TailwindCSS theo thiết kế Figma.\n"
                "Công ty SoftLab (T3/2021 - T9/2021) - Thực tập sinh Frontend (Frontend Intern)\n"
                "- Hỗ trợ cắt HTML/CSS và viết component React cơ bản dưới sự hướng dẫn của Mentor."
            ),
            reasoning=(
                "1. Xác định 2 công việc ở nhóm có giám sát (Supervised roles: Junior và Intern).\n"
                "2. job_1: 'Junior Frontend Developer' -> seniority_level='Junior'. "
                "raw_start_date='Tháng 10/2021' -> start_date='2021-10'; raw_end_date='2023' (chỉ có năm) -> chuẩn hóa thành '2023-01'.\n"
                "3. job_2: 'Thực tập sinh Frontend (Frontend Intern)' -> seniority_level='Intern'. "
                "raw_start_date='T3/2021' -> start_date='2021-03'; raw_end_date='T9/2021' -> end_date='2021-09'."
            ),
            job_blocks=[
                JobBlock(
                    job_id="job_1",
                    title="Junior Frontend Developer",
                    seniority_level=SeniorityLevel.JUNIOR,
                    raw_start_date="Tháng 10/2021",
                    raw_end_date="2023",
                    raw_quote="Công ty WebStudio (Tháng 10/2021 - 2023) - Junior Frontend Developer",
                    start_date="2021-10",
                    end_date="2023-01",
                    raw_text="Phát triển giao diện người dùng bằng Vue.js và TailwindCSS theo thiết kế Figma.",
                ),
                JobBlock(
                    job_id="job_2",
                    title="Thực tập sinh Frontend (Frontend Intern)",
                    seniority_level=SeniorityLevel.INTERN,
                    raw_start_date="T3/2021",
                    raw_end_date="T9/2021",
                    raw_quote="Công ty SoftLab (T3/2021 - T9/2021) - Thực tập sinh Frontend (Frontend Intern)",
                    start_date="2021-03",
                    end_date="2021-09",
                    raw_text="Hỗ trợ cắt HTML/CSS và viết component React cơ bản dưới sự hướng dẫn của Mentor.",
                ),
            ],
        ).with_inputs("cv_text"),

        # Example 4: Role promotion within the same company + historical dates for recency check
        dspy.Example(
            cv_text=(
                "Lê Quốc Bảo - System Administrator\n"
                "Công ty InfraTech Vietnam:\n"
                "* Senior System Engineer (06/2018 - 01/2020)\n"
                "  - Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.\n"
                "* Junior Sysadmin (06/2016 - 05/2018)\n"
                "  - Hỗ trợ quản trị server Linux cơ bản, theo dõi cảnh báo Nagios và xử lý sự cố mạng nội bộ."
            ),
            reasoning=(
                "1. Ứng viên thăng tiến qua 2 vị trí khác nhau trong cùng Công ty InfraTech Vietnam với 2 mốc thời gian và mức độ tự chủ khác nhau ('Senior' tự chủ = 1.0 vs 'Junior' có giám sát = 0.8).\n"
                "2. Phải tách thành 2 JobBlock độc lập: job_1 ('Senior System Engineer', 2018-06 đến 2020-01, Senior) và job_2 ('Junior Sysadmin', 2016-06 đến 2018-05, Junior).\n"
                "3. Đảm bảo raw_quote trích xuất nguyên văn từng dòng tiêu đề vị trí trong CV."
            ),
            job_blocks=[
                JobBlock(
                    job_id="job_1",
                    title="Senior System Engineer",
                    seniority_level=SeniorityLevel.SENIOR,
                    raw_start_date="06/2018",
                    raw_end_date="01/2020",
                    raw_quote="* Senior System Engineer (06/2018 - 01/2020)",
                    start_date="2018-06",
                    end_date="2020-01",
                    raw_text="Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.",
                ),
                JobBlock(
                    job_id="job_2",
                    title="Junior Sysadmin",
                    seniority_level=SeniorityLevel.JUNIOR,
                    raw_start_date="06/2016",
                    raw_end_date="05/2018",
                    raw_quote="* Junior Sysadmin (06/2016 - 05/2018)",
                    start_date="2016-06",
                    end_date="2018-05",
                    raw_text="Hỗ trợ quản trị server Linux cơ bản, theo dõi cảnh báo Nagios và xử lý sự cố mạng nội bộ.",
                ),
            ],
        ).with_inputs("cv_text"),

        # Example 5: Fresher CV with zero real work experience (Academic + Skills list only)
        dspy.Example(
            cv_text=(
                "Phạm Thu Hà - Sinh viên mới tốt nghiệp CNTT\n"
                "Học vấn: Cử nhân Công nghệ Thông tin - ĐH Công Nghệ (2020 - 2024)\n"
                "Chứng chỉ: AWS Certified Cloud Practitioner (2024)\n"
                "Kỹ năng chuyên môn: Docker, K8s, Git, Python, Sử dụng Figma cho thiết kế giao diện."
            ),
            reasoning=(
                "1. Phân tích toàn bộ CV: chỉ có thông tin Học vấn đại học, Chứng chỉ và danh sách Kỹ năng chuyên môn.\n"
                "2. Hoàn toàn không có khối kinh nghiệm làm việc thực tế (employment hay internship tại doanh nghiệp).\n"
                "3. Theo quy tắc nghiêm ngặt 'Work Experience Only', không được biến mục Học vấn hay Kỹ năng thành JobBlock. Trả về danh sách rỗng job_blocks=[]."
            ),
            job_blocks=[],
        ).with_inputs("cv_text"),
    ]


def get_gold_span_mapping_examples() -> List[dspy.Example]:
    """Return 5 diverse gold examples with Chain-of-Thought reasoning for SpanMappingSignature."""
    return [
        # Example 1: Standard mapping across job_1, job_2, and UNASSIGNED skill list
        dspy.Example(
            jobs_context=(
                "[job_1] DevOps Lead (2024-03 - None):\n"
                "Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.\n"
                "[job_2] DevOps Engineer (2019-06 - 2024-02):\n"
                "Quản lý cluster Kubernetes quy mô nhỏ, khoảng 10 services. Viết Terraform để provision hạ tầng AWS."
            ),
            spans_context=(
                "- Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.\n"
                "- Viết Terraform để provision hạ tầng AWS.\n"
                "- Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop."
            ),
            reasoning=(
                "1. Span 'Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.' nằm nguyên văn trong phần mô tả của [job_1] -> gán job_id='job_1'.\n"
                "2. Span 'Viết Terraform để provision hạ tầng AWS.' nằm trong phần mô tả của [job_2] -> gán job_id='job_2'.\n"
                "3. Span 'Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop.' là danh sách liệt kê kỹ năng chung, không thuộc [job_1] hay [job_2] -> gán job_id='UNASSIGNED'."
            ),
            span_mappings=[
                SpanMapping(
                    span="Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Viết Terraform để provision hạ tầng AWS.",
                    job_id="job_2",
                ),
                SpanMapping(
                    span="Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop.",
                    job_id=UNASSIGNED_JOB_ID,
                ),
            ],
        ).with_inputs("jobs_context", "spans_context"),

        # Example 2: Same skill across two overlapping jobs + ungrounded summary claim
        dspy.Example(
            jobs_context=(
                "[job_1] Senior Backend Developer (2022-01 - 2023-12):\n"
                "Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS. "
                "Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày.\n"
                "[job_2] Part-time Backend Consultant (2022-06 - 2023-06):\n"
                "Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python."
            ),
            spans_context=(
                "- Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS.\n"
                "- Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày\n"
                "- Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python.\n"
                "- Proficient in Java Core, Python, Redis"
            ),
            reasoning=(
                "1. Hai span đầu tiên ('Xây dựng hệ thống thanh toán bằng Python FastAPI...' và 'Xây dựng hệ thống message queue với Kafka...') thuộc mô tả của [job_1] -> gán job_id='job_1'.\n"
                "2. Span thứ ba ('Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python.') thuộc mô tả của [job_2] -> gán job_id='job_2'.\n"
                "3. Span thứ tư ('Proficient in Java Core, Python, Redis') là câu tự nhận xét chung ngoài các job blocks -> gán job_id='UNASSIGNED'."
            ),
            span_mappings=[
                SpanMapping(
                    span="Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS.",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Tối ưu hóa truy vấn SQL và xây dựng ETL pipeline bằng Python.",
                    job_id="job_2",
                ),
                SpanMapping(
                    span="Proficient in Java Core, Python, Redis",
                    job_id=UNASSIGNED_JOB_ID,
                ),
            ],
        ).with_inputs("jobs_context", "spans_context"),

        # Example 3: Job-specific tech stack line vs Global skills footer & Certifications
        dspy.Example(
            jobs_context=(
                "[job_1] Frontend Engineer (2021-10 - 2023-12):\n"
                "Phát triển SPA Dashboard bằng React.js và Redux. Tech stack dự án: React, TypeScript, GraphQL.\n"
                "[job_2] Frontend Intern (2021-03 - 2021-09):\n"
                "Hỗ trợ cắt giao diện HTML/CSS và chỉnh sửa giao diện Vue.js cơ bản."
            ),
            spans_context=(
                "- Phát triển SPA Dashboard bằng React.js và Redux.\n"
                "- Tech stack dự án: React, TypeScript, GraphQL.\n"
                "- Hỗ trợ cắt giao diện HTML/CSS và chỉnh sửa giao diện Vue.js cơ bản.\n"
                "- Chứng chỉ AWS Certified Cloud Practitioner (2024)\n"
                "- Kỹ năng tổng hợp: React, Vue, Angular, Docker"
            ),
            reasoning=(
                "1. Span 'Phát triển SPA Dashboard bằng React.js và Redux.' và 'Tech stack dự án: React, TypeScript, GraphQL.' đều nằm trực tiếp trong đoạn văn của [job_1] -> gán cả hai vào 'job_1'.\n"
                "2. Span 'Hỗ trợ cắt giao diện HTML/CSS và chỉnh sửa giao diện Vue.js cơ bản.' nằm trong [job_2] -> gán vào 'job_2'.\n"
                "3. Span chứng chỉ 'Chứng chỉ AWS Certified Cloud Practitioner (2024)' và danh sách cuối CV 'Kỹ năng tổng hợp: React, Vue, Angular, Docker' không thuộc job nào -> gán 'UNASSIGNED'."
            ),
            span_mappings=[
                SpanMapping(
                    span="Phát triển SPA Dashboard bằng React.js và Redux.",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Tech stack dự án: React, TypeScript, GraphQL.",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Hỗ trợ cắt giao diện HTML/CSS và chỉnh sửa giao diện Vue.js cơ bản.",
                    job_id="job_2",
                ),
                SpanMapping(
                    span="Chứng chỉ AWS Certified Cloud Practitioner (2024)",
                    job_id=UNASSIGNED_JOB_ID,
                ),
                SpanMapping(
                    span="Kỹ năng tổng hợp: React, Vue, Angular, Docker",
                    job_id=UNASSIGNED_JOB_ID,
                ),
            ],
        ).with_inputs("jobs_context", "spans_context"),

        # Example 4: Same-company promotion separating Senior vs Junior spans
        dspy.Example(
            jobs_context=(
                "[job_1] Senior System Engineer (2018-06 - 2020-01):\n"
                "Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.\n"
                "[job_2] Junior Sysadmin (2016-06 - 2018-05):\n"
                "Hỗ trợ quản trị server Linux cơ bản, theo dõi cảnh báo Nagios và xử lý sự cố mạng nội bộ."
            ),
            spans_context=(
                "- Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.\n"
                "- Hỗ trợ quản trị server Linux cơ bản"
            ),
            reasoning=(
                "1. Span 'Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.' thuộc giai đoạn Senior [job_1] -> gán job_id='job_1'.\n"
                "2. Span 'Hỗ trợ quản trị server Linux cơ bản' là cụm con nguyên văn nằm trong giai đoạn Junior [job_2] -> gán job_id='job_2'."
            ),
            span_mappings=[
                SpanMapping(
                    span="Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.",
                    job_id="job_1",
                ),
                SpanMapping(
                    span="Hỗ trợ quản trị server Linux cơ bản",
                    job_id="job_2",
                ),
            ],
        ).with_inputs("jobs_context", "spans_context"),

        # Example 5: Orphan spans when CV has no JobBlocks (Fresher / Academic CV)
        dspy.Example(
            jobs_context="",
            spans_context=(
                "- Docker, K8s, Git\n"
                "- Sử dụng Figma cho thiết kế giao diện"
            ),
            reasoning=(
                "1. jobs_context rỗng vì ứng viên chưa có kinh nghiệm làm việc thực tế (không có JobBlock nào).\n"
                "2. Theo quy tắc UNASSIGNED Boundary Rule, toàn bộ các evidence spans đều phải gán job_id='UNASSIGNED' và giữ nguyên văn từng chuỗi span."
            ),
            span_mappings=[
                SpanMapping(
                    span="Docker, K8s, Git",
                    job_id=UNASSIGNED_JOB_ID,
                ),
                SpanMapping(
                    span="Sử dụng Figma cho thiết kế giao diện",
                    job_id=UNASSIGNED_JOB_ID,
                ),
            ],
        ).with_inputs("jobs_context", "spans_context"),
    ]


def get_gold_span_richness_examples() -> List[dspy.Example]:
    """Return 6 diverse gold examples with Chain-of-Thought reasoning for SpanRichnessSignature."""
    return [
        # Example 1: Kubernetes — Lead architectural RICH_CONTEXT vs LIST_ONLY
        dspy.Example(
            skill_id="kubernetes",
            spans_text=(
                "- Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.\n"
                "- Kỹ năng: Docker, Kubernetes, Helm"
            ),
            reasoning=(
                "1. Span 'Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.' mô tả hành động kỹ thuật cụ thể ('Thiết kế và vận hành') kèm quy mô hệ thống thực tế ('50+ microservices') -> phân loại RICH_CONTEXT.\n"
                "2. Span 'Kỹ năng: Docker, Kubernetes, Helm' chỉ là danh sách từ khóa cách nhau bởi dấu phẩy, không có ngữ cảnh dự án -> phân loại LIST_ONLY."
            ),
            analyses=[
                SpanRichness(
                    span="Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices.",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Kỹ năng: Docker, Kubernetes, Helm",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),

        # Example 2: Kafka — High-throughput RICH_CONTEXT + Standard RICH_CONTEXT + LIST_ONLY
        dspy.Example(
            skill_id="kafka",
            spans_text=(
                "- Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày\n"
                "- Xây dựng hệ thống event streaming với Kafka 2 năm\n"
                "- Kỹ năng: Kafka, RabbitMQ, Redis"
            ),
            reasoning=(
                "1. Span 'Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày' có hành động xây dựng hệ thống và chỉ số thông lượng sản phẩm thực tế (1M event/ngày) -> RICH_CONTEXT.\n"
                "2. Span 'Xây dựng hệ thống event streaming với Kafka 2 năm' nêu rõ ứng dụng thực tế xây dựng event streaming -> RICH_CONTEXT.\n"
                "3. Span 'Kỹ năng: Kafka, RabbitMQ, Redis' chỉ liệt kê tên công nghệ -> LIST_ONLY."
            ),
            analyses=[
                SpanRichness(
                    span="Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Xây dựng hệ thống event streaming với Kafka 2 năm",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Kỹ năng: Kafka, RabbitMQ, Redis",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),

        # Example 3: Java — Practical project RICH_CONTEXT vs ungrounded self-claim LIST_ONLY
        dspy.Example(
            skill_id="java",
            spans_text=(
                "- Lập trình backend bằng Java Spring Boot trong 2 năm\n"
                "- Proficient in Java Core"
            ),
            reasoning=(
                "1. Span 'Lập trình backend bằng Java Spring Boot trong 2 năm' mô tả công việc thực tế phát triển backend với framework cụ thể -> RICH_CONTEXT.\n"
                "2. Span 'Proficient in Java Core' chỉ là câu tự nhận định mức độ thành thạo suông mà không nêu bất kỳ dự án hay tác vụ thực tế nào -> theo quy tắc nghiêm ngặt phải phân loại là LIST_ONLY."
            ),
            analyses=[
                SpanRichness(
                    span="Lập trình backend bằng Java Spring Boot trong 2 năm",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Proficient in Java Core",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),

        # Example 4: Linux — AMBIGUOUS passive support vs RICH_CONTEXT automation
        dspy.Example(
            skill_id="linux",
            spans_text=(
                "- Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.\n"
                "- Tham gia hỗ trợ môi trường server Linux cơ bản cùng team vận hành"
            ),
            reasoning=(
                "1. Span 'Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.' mô tả tác vụ kỹ thuật chuyên sâu và quy mô 100+ server -> RICH_CONTEXT.\n"
                "2. Span 'Tham gia hỗ trợ môi trường server Linux cơ bản cùng team vận hành' diễn đạt mơ hồ ('Tham gia hỗ trợ... cơ bản'), không rõ ứng viên trực tiếp làm tác vụ gì -> AMBIGUOUS."
            ),
            analyses=[
                SpanRichness(
                    span="Tự động hóa cấu hình 100+ server Linux bằng Ansible và thiết kế hệ thống lưu trữ HA.",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Tham gia hỗ trợ môi trường server Linux cơ bản cùng team vận hành",
                    richness_label=RichnessLabel.AMBIGUOUS,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),

        # Example 5: GCP — Pure LIST_ONLY spans
        dspy.Example(
            skill_id="gcp",
            spans_text=(
                "- Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop.\n"
                "- Cloud Platforms: AWS, GCP, Azure"
            ),
            reasoning=(
                "1. Cả hai span đều là danh sách liệt kê tên công nghệ cách nhau bằng dấu phẩy, hoàn toàn không có động từ hành động hay ngữ cảnh dự án.\n"
                "2. Phân loại cả hai là LIST_ONLY."
            ),
            analyses=[
                SpanRichness(
                    span="Kỹ năng khác: Python, Bash, Ansible, GCP, Photoshop.",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
                SpanRichness(
                    span="Cloud Platforms: AWS, GCP, Azure",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),

        # Example 6: React — All 3 labels (RICH_CONTEXT, AMBIGUOUS, LIST_ONLY) in one skill
        dspy.Example(
            skill_id="react",
            spans_text=(
                "- Phát triển SPA Dashboard bằng React.js và Redux, tối ưu thời gian tải trang giảm 40%.\n"
                "- Có tìm hiểu và hỗ trợ chỉnh sửa giao diện React nhỏ lẻ trong thời gian thực tập.\n"
                "- Kỹ năng tổng hợp: React, Vue, Angular, Docker"
            ),
            reasoning=(
                "1. Span 1 mô tả rõ việc phát triển SPA Dashboard bằng React.js/Redux kèm kết quả định lượng (giảm 40% thời gian tải trang) -> RICH_CONTEXT.\n"
                "2. Span 2 nêu mức độ tiếp xúc sơ khởi, thụ động ('Có tìm hiểu và hỗ trợ chỉnh sửa... nhỏ lẻ') -> AMBIGUOUS.\n"
                "3. Span 3 là danh sách từ khóa tổng hợp cuối CV -> LIST_ONLY."
            ),
            analyses=[
                SpanRichness(
                    span="Phát triển SPA Dashboard bằng React.js và Redux, tối ưu thời gian tải trang giảm 40%.",
                    richness_label=RichnessLabel.RICH_CONTEXT,
                ),
                SpanRichness(
                    span="Có tìm hiểu và hỗ trợ chỉnh sửa giao diện React nhỏ lẻ trong thời gian thực tập.",
                    richness_label=RichnessLabel.AMBIGUOUS,
                ),
                SpanRichness(
                    span="Kỹ năng tổng hợp: React, Vue, Angular, Docker",
                    richness_label=RichnessLabel.LIST_ONLY,
                ),
            ],
        ).with_inputs("skill_id", "spans_text"),
    ]


def get_dspy_trainset_and_valset(
    train_ratio: float = 0.8,
) -> Dict[str, Tuple[List[dspy.Example], List[dspy.Example]]]:
    """
    Return (trainset, valset) splits for each of the 4 DSPy tasks in Module 2.
    Ensures deterministic splitting for reproducible research benchmarking.
    """
    all_sets = {
        "job_extractor": get_gold_job_extraction_examples(),
        "span_mapper": get_gold_span_mapping_examples(),
        "jd_parser": get_gold_jd_requirement_examples(),
        "span_richness": get_gold_span_richness_examples(),
    }
    splits: Dict[str, Tuple[List[dspy.Example], List[dspy.Example]]] = {}
    for key, examples in all_sets.items():
        n_train = max(1, int(round(len(examples) * train_ratio)))
        if n_train >= len(examples) and len(examples) > 1:
            n_train = len(examples) - 1
        trainset = examples[:n_train]
        valset = examples[n_train:] if len(examples) > 1 else examples
        splits[key] = (trainset, valset)
    return splits
