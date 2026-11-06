"""
Gold Dataset of Curated Interview Examples for DSPy Teleprompter Optimization.
Supports Phase 4 / NCKH reproducibility via declarative `dspy.Example` instances.

Expanded, scientifically validated dataset covering:
  - All Metamorphic Relations: INVARIANT, MINOR_SHIFT, MODERATE_SHIFT, DECISIVE_SHIFT (Low & High).
  - All Strategies: PROBE_DEPTH, COMPARE_SUBSTITUTE, LEARNING_AGILITY.
  - Multi-turn Progression: k = 1 (primary competency slot) and k = 2 (dynamic probing sub-slots).
  - High-demand Technical Domains: Spring Boot, Kubernetes, Kafka, Terraform, PostgreSQL, Go, Docker, etc.
  - Strict Single-Intent constraint (One-Question-One-Answer without compounding).
  - Train/Dev split support for quantitative held-out evaluation.
"""

from typing import List, Literal
import dspy

from adaptive_questioning.schemas.api_models import ProposedSubSlot
from adaptive_questioning.schemas.state import MetamorphicTag


# ===========================================================================
# STEP 2A: QUESTION GENERATOR GOLD EXAMPLES (20 CURATED SAMPLES)
# ===========================================================================

def get_gold_question_examples(
    split: Literal["all", "train", "dev", "val"] = "all",
) -> List[dspy.Example]:
    """
    Curated few-shot demonstrations for Step 2A (Abductive Question Generator).
    Enforces One-Question-One-Answer, Show-Don't-Tell, and Contextual Bridging.
    Train: 14 examples | Dev: 6 examples | All: 20 examples.
    """
    examples = [
        # 1. Java Spring (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `java_spring` (Matched CV Skill: `java_spring`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.30 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3925, 0.4126, 0.1949]\n"
                "- Bằng chứng nguyên văn từ CV: \"Phát triển các RESTful API CRUD cơ bản sử dụng Java Spring Boot và Spring Data JPA.\"\n"
                "- Ngữ cảnh công việc: Junior Java Developer (01/2022 - 05/2023)\n"
                "- Context Anchors bắc cầu (A_ctx):\n"
                "  1. [INITIAL_NONE] Skill: postgresql | s_cv=4.00 | Job: Backend Developer (06/2023 - Hiện tại)\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng java_spring tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior Technical Interviewer / Principal Engineer phỏng vấn bằng tiếng Việt chuyên nghiệp.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó (r_target): Đo lường đúng ngưỡng 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell, kết nối tự nhiên với Context Anchor postgresql."
            ),
            surprising_fact_C=(
                "CV chỉ ghi nhận kinh nghiệm CRUD cơ bản với Java Spring Boot (s_cv=2.30), trong khi JD yêu cầu "
                "mức độ chuyên sâu 4.00, và ứng viên lại có nền tảng PostgreSQL rất mạnh (s_cv=4.00) ở công việc hiện tại."
            ),
            hypothesis_A=(
                "Ứng viên có thể đã làm việc với các hệ thống backend kết nối DB quy mô lớn nhưng chủ yếu dựa vào "
                "kỹ năng viết SQL tối ưu, chưa thực sự nắm sâu cơ chế quản lý Transaction nội tại của Spring (@Transactional, "
                "Propagation, Isolation, Rollback behavior)."
            ),
            new_sub_slot=None,
            target_slot_id="java_spring:primary",
            question=(
                "Trong các dự án backend sử dụng Spring Boot và PostgreSQL, khi một phương thức được đánh dấu @Transactional "
                "gặp ngoại lệ runtime giữa chừng, anh/chị cấu hình cơ chế rollback và quản lý propagation như thế nào để đảm bảo tính toàn vẹn dữ liệu?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 2. Terraform (k=1, COMPARE_SUBSTITUTE)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `terraform` (Matched CV Skill: `cloudformation`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.40 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3689, 0.4286, 0.2024]\n"
                "- Bằng chứng nguyên văn từ CV: \"Tự động hóa cấp phát hạ tầng AWS bằng CloudFormation templates.\"\n"
                "- Ngữ cảnh công việc: Cloud Engineer (06/2021 - 02/2024)\n"
                "- Context Anchors bắc cầu (A_ctx):\n"
                "  1. [INITIAL_NONE] Skill: kubernetes | s_cv=4.50 | Job: DevOps Lead (03/2024 - Hiện tại)\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng terraform tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior Technical Interviewer / Principal Engineer phỏng vấn bằng tiếng Việt chuyên nghiệp.\n"
                "- Chiến lược phỏng vấn: So sánh kỹ năng thay thế (COMPARE_SUBSTITUTE) giữa CloudFormation và Terraform.\n"
                "- Hiệu chỉnh độ khó (r_target): Đo lường đúng ngưỡng 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell, kết nối tự nhiên với Context Anchor kubernetes."
            ),
            surprising_fact_C=(
                "Ứng viên đạt năng lực chuyên gia về Kubernetes (s_cv=4.50) nhưng về IaC lại chỉ có kinh nghiệm "
                "với CloudFormation (s_cv=2.40) thay vì công cụ Terraform theo yêu cầu của JD."
            ),
            hypothesis_A=(
                "Ứng viên đã quen với tư duy hạ tầng dạng mã nguồn (IaC) trên AWS thông qua CloudFormation, "
                "nhưng có thể chưa va chạm với các bài toán đặc thù của Terraform như State Locking từ xa, "
                "quản lý Drift, hoặc thiết kế Modular hạ tầng đa môi trường."
            ),
            new_sub_slot=None,
            target_slot_id="terraform:primary",
            question=(
                "Từ kinh nghiệm tự động hóa hạ tầng bằng CloudFormation trước đây và quản lý cụm Kubernetes hiện tại, "
                "khi chuyển sang dùng Terraform cho nhiều thành viên cùng thao tác, anh/chị thiết kế cơ chế Remote Backend "
                "kết hợp State Locking như thế nào để ngăn chặn xung đột trạng thái hạ tầng?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 3. English Technical Triage (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `english` (Matched CV Skill: `english`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 3.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.00 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.4658, 0.3628, 0.1714]\n"
                "- Bằng chứng nguyên văn từ CV: \"Đọc hiểu tài liệu kỹ thuật tiếng Anh cơ bản.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (06/2023 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): Các dự án Backend thực tế\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng english tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior Technical Interviewer / Principal Engineer.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH) cho kỹ năng ngoại ngữ chuyên ngành.\n"
                "- Hiệu chỉnh độ khó: Đọc hiểu tài liệu kỹ thuật độc lập (3.50/5.0).\n"
                "- Ràng buộc: Đặt câu hỏi cụ thể về cách tiếp cận khi gặp lỗi hoặc tài liệu chuyên ngành phức tạp."
            ),
            surprising_fact_C=(
                "Ứng viên làm Backend Developer ở dự án hiện tại nhưng tự khai tiếng Anh chỉ ở mức đọc hiểu cơ bản (2.00), "
                "thấp hơn yêu cầu tự chủ đọc tài liệu kỹ thuật chuyên sâu của JD (3.50)."
            ),
            hypothesis_A=(
                "Ứng viên có thể gặp rào cản khi đọc tài liệu mở rộng hoặc log lỗi bằng tiếng Anh và phải phụ thuộc vào "
                "công cụ dịch máy thay vì tự tin phân tích trực tiếp."
            ),
            new_sub_slot=None,
            target_slot_id="english:primary",
            question=(
                "Khi gặp một thông báo lỗi nghiêm trọng từ thư viện bên thứ ba viết bằng tiếng Anh kỹ thuật chuyên sâu "
                "mà tài liệu không có giải thích rõ ràng, anh/chị áp dụng quy trình phân tích và tra cứu trực tiếp như thế nào để xác định chính xác nguyên nhân gốc?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 4. Kubernetes (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `kubernetes` (Matched CV Skill: `kubernetes`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 3.00 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.2429, 0.5142, 0.2429]\n"
                "- Bằng chứng nguyên văn từ CV: \"Triển khai ứng dụng lên Kubernetes cluster bằng Helm chart.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (03/2023 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): 1. [INITIAL_NONE] Skill: docker | s_cv=4.00\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng kubernetes tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Principal DevOps / SRE Lead.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Đo lường mức chuyên gia vận hành production (4.50/5.0).\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên đã dùng Docker rất vững (4.00) và dùng Helm trên K8s, nhưng điểm CV K8s chỉ ở mức 3.00 "
                "so với yêu cầu vận hành production khắt khe 4.50 của JD."
            ),
            hypothesis_A=(
                "Ứng viên có thể chỉ viết manifests và deploy ở mức cơ bản, chưa từng trực tiếp điều tra và khắc phục "
                "các sự cố runtime nghiêm trọng như Pod bị OOMKilled hay thiết lập QoS Class phù hợp."
            ),
            new_sub_slot=None,
            target_slot_id="kubernetes:primary",
            question=(
                "Trong môi trường production, khi một Pod xử lý tác vụ nặng liên tục bị restart với exit code 137 (OOMKilled), "
                "anh/chị tiến hành các bước điều tra và cấu hình lại resource requests/limits ra sao để ngăn chặn triệt để sự cố này?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 5. Kafka (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `kafka` (Matched CV Skill: `rabbitmq`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.50 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3460, 0.4442, 0.2098]\n"
                "- Bằng chứng nguyên văn từ CV: \"Sử dụng RabbitMQ để xử lý hàng đợi tin nhắn giữa các microservices.\"\n"
                "- Ngữ cảnh công việc: Backend Engineer (05/2022 - 01/2024)\n"
                "- Context Anchors bắc cầu (A_ctx): 1. [INITIAL_NONE] Skill: java_spring | s_cv=4.00\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng kafka tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior Distributed Systems Architect.\n"
                "- Chiến lược phỏng vấn: So sánh kỹ năng thay thế (COMPARE_SUBSTITUTE).\n"
                "- Hiệu chỉnh độ khó: Mức độ làm chủ hệ thống streaming quy mô lớn (4.00/5.0).\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên có kinh nghiệm với RabbitMQ nhưng vị trí tuyển dụng yêu cầu Kafka ở quy mô sự kiện lớn, "
                "với đặc tính lưu trữ log phân tán hoàn toàn khác với message broker truyền thống."
            ),
            hypothesis_A=(
                "Ứng viên có thể mang tư duy message queue hàng đợi tạm thời sang Kafka, chưa nắm rõ cơ chế phân chia "
                "Partition, Consumer Group và hiện tượng Consumer Lag."
            ),
            new_sub_slot=None,
            target_slot_id="kafka:primary",
            question=(
                "Khi hệ thống streaming gặp tình trạng Consumer Lag tăng đột biến tại một topic có lưu lượng lớn, "
                "anh/chị phân tích nguyên nhân và điều chỉnh cơ chế tiêu thụ tin nhắn trong Consumer Group như thế nào để giải tỏa tắc nghẽn?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 6. PostgreSQL (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `postgresql` (Matched CV Skill: `postgresql`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.80 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.2810, 0.4855, 0.2335]\n"
                "- Bằng chứng nguyên văn từ CV: \"Thiết kế cơ sở dữ liệu quan hệ PostgreSQL và viết câu truy vấn SQL.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (08/2022 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): Các dịch vụ API hiện hành\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng postgresql tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Database Performance Engineer / Principal Backend.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Đo lường kỹ năng tối ưu truy vấn thực chiến (4.00/5.0).\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "CV ghi thiết kế CSDL và viết SQL nhưng không đề cập đến kinh nghiệm tuning, tối ưu hóa chỉ mục hay giải quyết nghẽn I/O."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa từng phân tích Query Plan bằng EXPLAIN ANALYZE trên các bảng dữ liệu hàng triệu dòng để tối ưu chỉ mục composite."
            ),
            new_sub_slot=None,
            target_slot_id="postgresql:primary",
            question=(
                "Khi một câu truy vấn báo cáo phức tạp trên bảng dữ liệu hàng triệu dòng bị phản hồi chậm, "
                "anh/chị dùng công cụ EXPLAIN ANALYZE để đọc các chỉ số then chốt nào nhằm quyết định chiến lược đánh chỉ mục phù hợp?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 7. Redis (k=1, COMPARE_SUBSTITUTE)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `redis` (Matched CV Skill: `memcached`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 3.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.20 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.4182, 0.3956, 0.1862]\n"
                "- Bằng chứng nguyên văn từ CV: \"Sử dụng Memcached để lưu tạm session và dữ liệu bộ nhớ đệm.\"\n"
                "- Ngữ cảnh công việc: Web Developer (01/2021 - 12/2022)\n"
                "- Context Anchors bắc cầu (A_ctx): Dự án Web Thương mại điện tử\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng redis tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Technical Lead.\n"
                "- Chiến lược phỏng vấn: So sánh kỹ năng thay thế (COMPARE_SUBSTITUTE).\n"
                "- Hiệu chỉnh độ khó: Mức 3.50/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên mới chỉ dùng Memcached cho cache đơn giản, trong khi JD yêu cầu Redis phục vụ kiến trúc cache nâng cao."
            ),
            hypothesis_A=(
                "Ứng viên chưa từng áp dụng các cấu trúc dữ liệu phong phú của Redis hoặc chưa có kinh nghiệm xử lý hiện tượng Cache Stampede khi key hết hạn đồng loạt."
            ),
            new_sub_slot=None,
            target_slot_id="redis:primary",
            question=(
                "Khi chuyển đổi từ mô hình cache đơn giản sang Redis, anh/chị thiết kế giải pháp như thế nào để ngăn chặn hiện tượng Cache Stampede khi một key có lượng truy cập rất lớn bất ngờ hết hạn?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 8. Docker (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `docker` (Matched CV Skill: `docker`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 3.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.50 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3460, 0.4442, 0.2098]\n"
                "- Bằng chứng nguyên văn từ CV: \"Sử dụng Docker đóng gói ứng dụng Node.js.\"\n"
                "- Ngữ cảnh công việc: Junior Developer (06/2022 - 04/2023)\n"
                "- Context Anchors bắc cầu (A_ctx): Dự án Node.js API\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng docker tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior DevOps Engineer.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 3.50/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "CV chỉ ghi dùng Docker đóng gói cơ bản, trong khi production yêu cầu tối ưu hóa dung lượng image và bảo mật container."
            ),
            hypothesis_A=(
                "Ứng viên có thể chỉ copy toàn bộ source code vào một image cơ bản lớn, chưa áp dụng Multi-stage build hay cơ chế layer cache để tối ưu kích thước."
            ),
            new_sub_slot=None,
            target_slot_id="docker:primary",
            question=(
                "Để giảm thiểu kích thước Docker image của ứng dụng từ hàng trăm megabyte xuống mức tối thiểu và tăng tốc độ CI build, "
                "anh/chị đã áp dụng kỹ thuật Multi-stage build cụ thể như thế nào trong Dockerfile?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 9. Golang Concurrency (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `golang` (Matched CV Skill: `golang`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.60 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3235, 0.4608, 0.2157]\n"
                "- Bằng chứng nguyên văn từ CV: \"Phát triển microservice xử lý dữ liệu bằng Go.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (10/2022 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): Hệ thống backend xử lý dữ liệu\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng golang tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Lead Systems Engineer.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên viết Go cho microservice nhưng CV không thể hiện cách quản lý concurrency an toàn, vốn là cốt lõi của Go trong backend tải cao."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa từng đối mặt với hiện tượng Goroutine leak hoặc race condition khi sử dụng channel và sync primitives dưới tải lớn."
            ),
            new_sub_slot=None,
            target_slot_id="golang:primary",
            question=(
                "Trong một service viết bằng Go xử lý hàng ngàn tác vụ đồng thời, anh/chị sử dụng công cụ hoặc mẫu thiết kế nào "
                "để phát hiện và kiểm soát việc rò rỉ goroutine (goroutine leak) khi các channel không được đóng đúng cách?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 10. AWS Solution Architect (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `aws` (Matched CV Skill: `aws`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.70 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3021, 0.4745, 0.2234]\n"
                "- Bằng chứng nguyên văn từ CV: \"Sử dụng EC2, S3 và RDS để vận hành ứng dụng trên AWS.\"\n"
                "- Ngữ cảnh công việc: Infrastructure Support (02/2022 - 11/2023)\n"
                "- Context Anchors bắc cầu (A_ctx): Dự án triển khai AWS\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng aws tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: AWS Solutions Architect Professional.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "CV liệt kê các dịch vụ EC2, S3, RDS nhưng chỉ ở mức hỗ trợ vận hành, chưa thể hiện năng lực thiết kế hạ tầng có độ sẵn sàng cao (High Availability)."
            ),
            hypothesis_A=(
                "Ứng viên có thể chỉ thao tác trên AWS Management Console đơn lẻ, chưa có kinh nghiệm thiết lập kiến trúc Multi-AZ tự động failover cho cơ sở dữ liệu và tải ứng dụng."
            ),
            new_sub_slot=None,
            target_slot_id="aws:primary",
            question=(
                "Khi thiết kế kiến trúc hệ thống trên AWS yêu cầu khả năng chịu lỗi cao (High Availability), "
                "anh/chị cấu hình cơ chế Multi-AZ failover giữa Application Load Balancer và RDS như thế nào để đảm bảo thời gian gián đoạn là tối thiểu khi một Availability Zone gặp sự cố?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 11. ReactJS Optimization (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `reactjs` (Matched CV Skill: `reactjs`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.50 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3460, 0.4442, 0.2098]\n"
                "- Bằng chứng nguyên văn từ CV: \"Xây dựng giao diện người dùng web sử dụng ReactJS và Redux.\"\n"
                "- Ngữ cảnh công việc: Frontend Developer (05/2022 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): Dự án Dashboard quản trị\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng reactjs tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Senior Frontend Architect.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên làm React hơn 1 năm với Redux nhưng CV không đề cập đến kinh nghiệm đo lường hiệu năng hay giải quyết hiện tượng re-render thừa."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa thành thạo việc sử dụng React Profiler để xác định các component bị re-render không cần thiết trong cây component phân cấp sâu."
            ),
            new_sub_slot=None,
            target_slot_id="reactjs:primary",
            question=(
                "Khi một màn hình dashboard hiển thị lượng lớn dữ liệu bị giật lag do render lại liên tục, "
                "anh/chị dùng công cụ React DevTools Profiler như thế nào để khoanh vùng nguyên nhân và tối ưu hóa việc truyền props giữa các component?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 12. CI/CD Pipeline (k=1, COMPARE_SUBSTITUTE)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `ci_cd` (Matched CV Skill: `jenkins`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 3.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.40 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3689, 0.4286, 0.2024]\n"
                "- Bằng chứng nguyên văn từ CV: \"Cấu hình Jenkins job để tự động build và deploy mã nguồn.\"\n"
                "- Ngữ cảnh công việc: Software Engineer (09/2021 - 03/2023)\n"
                "- Context Anchors bắc cầu (A_ctx): Hệ thống tự động hóa build\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng ci_cd tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: DevOps Lead.\n"
                "- Chiến lược phỏng vấn: So sánh kỹ năng thay thế (COMPARE_SUBSTITUTE).\n"
                "- Hiệu chỉnh độ khó: Mức 3.50/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên có kinh nghiệm với Jenkins truyền thống nhưng dự án yêu cầu xây dựng pipeline hiện đại bằng GitLab CI dạng declarative mã nguồn."
            ),
            hypothesis_A=(
                "Ứng viên quen với cấu hình UI của Jenkins, có thể chưa nắm rõ cách quản lý cache dependencies và artifacts giữa các stage song song trong file YAML."
            ),
            new_sub_slot=None,
            target_slot_id="ci_cd:primary",
            question=(
                "Khi chuyển đổi quy trình build từ Jenkins sang sử dụng GitLab CI (.gitlab-ci.yml), "
                "anh/chị cấu hình cơ chế caching dependencies giữa các job như thế nào để rút ngắn thời gian thực thi của toàn bộ pipeline?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 13. System Design Rate Limiting (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `system_design` (Matched CV Skill: `system_design`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.80 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.2810, 0.4855, 0.2335]\n"
                "- Bằng chứng nguyên văn từ CV: \"Tham gia thiết kế kiến trúc các dịch vụ backend phục vụ người dùng.\"\n"
                "- Ngữ cảnh công việc: Senior Backend (01/2023 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): 1. [INITIAL_NONE] Skill: redis | s_cv=4.00\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng system_design tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Principal Architect.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 4.50/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên tham gia thiết kế backend nhưng CV chưa có bằng chứng giải quyết các bài toán bảo vệ hệ thống trước lưu lượng đột biến ở quy mô lớn."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa từng trực tiếp thiết kế giải pháp Rate Limiting phân tán bằng thuật toán Token Bucket hoặc Sliding Window Log."
            ),
            new_sub_slot=None,
            target_slot_id="system_design:primary",
            question=(
                "Để bảo vệ cụm microservices khỏi nguy cơ quá tải khi gặp các đợt lưu lượng truy cập đột biến (traffic spike), "
                "anh/chị thiết kế cơ chế Rate Limiting phân tán sử dụng Redis với thuật toán cụ thể nào để đảm bảo tính công bằng và chính xác?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 14. GraphQL N+1 Problem (k=1, COMPARE_SUBSTITUTE)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `graphql` (Matched CV Skill: `rest_api`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.40 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3689, 0.4286, 0.2024]\n"
                "- Bằng chứng nguyên văn từ CV: \"Xây dựng hệ thống REST API theo chuẩn OpenAPI.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (03/2022 - 08/2023)\n"
                "- Context Anchors bắc cầu (A_ctx): Hệ thống API dịch vụ\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng graphql tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Lead API Architect.\n"
                "- Chiến lược phỏng vấn: So sánh kỹ năng thay thế (COMPARE_SUBSTITUTE).\n"
                "- Hiệu chỉnh độ khó: Mức 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên chỉ thuần thục REST API nhưng JD yêu cầu kiến trúc GraphQL giải quyết bài toán over-fetching và under-fetching."
            ),
            hypothesis_A=(
                "Ứng viên chuyển từ tư duy REST sang GraphQL dễ mắc bẫy N+1 query trong các resolver lồng nhau nếu chưa nắm cơ chế DataLoader."
            ),
            new_sub_slot=None,
            target_slot_id="graphql:primary",
            question=(
                "Khi xây dựng API bằng GraphQL, làm thế nào anh/chị áp dụng cơ chế Batching và Caching của thư viện DataLoader "
                "trong các resolver lồng nhau để giải quyết triệt để vấn đề N+1 query xuống cơ sở dữ liệu?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # ===================================================================
        # DEV / EVALUATION SPLIT (EXAMPLES 15 - 20)
        # ===================================================================

        # 15. Elasticsearch (k=1, LEARNING_AGILITY)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `elasticsearch` (Matched CV Skill: `postgresql`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 3.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.00 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.4658, 0.3628, 0.1714]\n"
                "- Bằng chứng nguyên văn từ CV: \"Tìm kiếm dữ liệu toàn văn bằng tính năng Full-text search của PostgreSQL.\"\n"
                "- Ngữ cảnh công việc: Backend Developer (06/2022 - Hiện tại)\n"
                "- Context Anchors bắc cầu (A_ctx): Dự án tìm kiếm dữ liệu sản phẩm\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng elasticsearch tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Search Engineering Lead.\n"
                "- Chiến lược phỏng vấn: Khả năng học hỏi thích ứng kỹ thuật (LEARNING_AGILITY).\n"
                "- Hiệu chỉnh độ khó: Mức 3.50/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên có kiến thức cơ bản về tìm kiếm toàn văn trên RDBMS nhưng chưa có kinh nghiệm thực tế với công cụ tìm kiếm chuyên dụng Elasticsearch."
            ),
            hypothesis_A=(
                "Ứng viên cần hiểu nguyên lý cấu trúc chỉ mục đảo (Inverted Index) và cơ chế Tokenizer/Analyzer của Elasticsearch khi chuyển giao giải pháp."
            ),
            new_sub_slot=None,
            target_slot_id="elasticsearch:primary",
            question=(
                "Dựa trên nguyên lý Inverted Index của Elasticsearch, anh/chị lựa chọn bộ Analyzer và cấu hình Tokenizer ra sao "
                "để hệ thống có thể tìm kiếm chính xác các cụm từ kỹ thuật không phân biệt dấu và chữ hoa chữ thường?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 16. Microservices Security (k=1, PROBE_DEPTH)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `microservices_security` (Matched CV Skill: `jwt`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.50 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3460, 0.4442, 0.2098]\n"
                "- Bằng chứng nguyên văn từ CV: \"Xác thực người dùng bằng JSON Web Token (JWT).\"\n"
                "- Ngữ cảnh công việc: Backend Developer (01/2022 - 12/2023)\n"
                "- Context Anchors bắc cầu (A_ctx): Cổng xác thực người dùng\n"
                "- Lịch sử hội thoại: (Bắt đầu phỏng vấn kỹ năng microservices_security tại local turn k=1)"
            ),
            main_layer_directives=(
                "- Persona: Application Security Specialist.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH).\n"
                "- Hiệu chỉnh độ khó: Mức 4.00/5.0.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "CV ghi nhận dùng JWT để xác thực nhưng không làm rõ cách xử lý thu hồi token (token revocation) hoặc xoay vòng refresh token."
            ),
            hypothesis_A=(
                "Ứng viên có thể chỉ sinh token tĩnh với hạn dài mà chưa có cơ chế thu hồi token tức thì khi tài khoản có dấu hiệu bị xâm nhập."
            ),
            new_sub_slot=None,
            target_slot_id="microservices_security:primary",
            question=(
                "Vì JWT có tính chất stateless, trong trường hợp một Access Token bị lộ trước khi hết hạn, "
                "anh/chị thiết kế giải pháp thu hồi quyền truy cập (Token Revocation) tức thời ở API Gateway như thế nào?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 17. Java Spring (k=2, PROBE_DEPTH - Probing Sub-slot 1)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `java_spring` (Matched CV Skill: `java_spring`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.30 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3689, 0.4286, 0.2024]\n"
                "- Bằng chứng nguyên văn từ CV: \"Phát triển các RESTful API CRUD cơ bản sử dụng Java Spring Boot...\"\n"
                "- Ngữ cảnh công việc: Junior Java Developer\n"
                "- Lịch sử hội thoại:\n"
                "- [Turn t=1, k=1, Skill='java_spring', Slot='java_spring:primary']\n"
                "  + Câu hỏi: Cấu hình rollback cho @Transactional khi gặp runtime exception?\n"
                "  + Trả lời: Em dùng @Transactional(rollbackFor = Exception.class) trên Service.\n"
                "  + Judge Insight: Ứng viên nắm được cú pháp cơ bản cho local transaction đơn lẻ. (Tag=MINOR_SHIFT)"
            ),
            main_layer_directives=(
                "- Persona: Senior Technical Interviewer.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH) tại lượt hỏi xoáy k=2.\n"
                "- Quản lý Probing Sub-slot: Sinh 1 sub-slot mới để kiểm tra giao dịch phân tán (distributed transaction).\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên trả lời tốt về local transaction ở lượt k=1, nhưng chưa rõ năng lực xử lý giao dịch trải rộng qua nhiều microservices."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa từng triển khai các mô hình đảm bảo tính nhất quán dữ liệu phân tán như Saga Pattern hay Outbox Pattern."
            ),
            new_sub_slot=ProposedSubSlot(
                slot_name="distributed_tx",
                description="Khả năng thiết kế và xử lý tính nhất quán dữ liệu phân tán (Saga / Outbox Pattern)",
            ),
            target_slot_id="java_spring:sub_1",
            question=(
                "Khi một nghiệp vụ thanh toán đòi hỏi cập nhật trạng thái đồng thời trên hai microservices độc lập, "
                "anh/chị áp dụng mô hình Saga Pattern (Choreography hoặc Orchestration) như thế nào để xử lý giao dịch bù (Compensating Transaction) nếu bước cuối cùng thất bại?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 18. Kafka (k=2, PROBE_DEPTH - Probing Sub-slot 1)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `kafka` (Matched CV Skill: `rabbitmq`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.50 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.3120, 0.4680, 0.2200]\n"
                "- Bằng chứng nguyên văn từ CV: \"Sử dụng RabbitMQ xử lý message queue.\"\n"
                "- Lịch sử hội thoại:\n"
                "- [Turn t=2, k=1, Skill='kafka', Slot='kafka:primary']\n"
                "  + Câu hỏi: Xử lý consumer lag khi topic lưu lượng lớn?\n"
                "  + Trả lời: Em tăng số partition và scale thêm instance trong consumer group.\n"
                "  + Judge Insight: Ứng viên hiểu cơ chế scale partition của Kafka. (Tag=MODERATE_SHIFT)"
            ),
            main_layer_directives=(
                "- Persona: Lead Architect.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH) tại lượt k=2.\n"
                "- Quản lý Probing Sub-slot: Sinh 1 sub-slot mới để kiểm tra Exactly-once delivery.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên biết cách scale consumer group nhưng chưa làm rõ việc xử lý trùng lặp tin nhắn khi broker rebalance."
            ),
            hypothesis_A=(
                "Ứng viên có thể dựa vào At-least-once mặc định mà chưa thiết kế cơ chế Idempotent Consumer để loại trừ tin nhắn bị gửi lại."
            ),
            new_sub_slot=ProposedSubSlot(
                slot_name="idempotent_processing",
                description="Kỹ thuật đảm bảo xử lý tin nhắn trùng lặp (Idempotent Consumer) khi có rebalancing",
            ),
            target_slot_id="kafka:sub_1",
            question=(
                "Trong trường hợp mạng chập chờn khiến Kafka Broker gửi lại các message đã được tiêu thụ, "
                "anh/chị thiết kế cơ chế Idempotent Consumer ở tầng ứng dụng như thế nào để đảm bảo không bị xử lý trùng lặp dữ liệu giao dịch?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 19. Kubernetes (k=2, PROBE_DEPTH - Probing Sub-slot 1)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `kubernetes` (Matched CV Skill: `kubernetes`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.50 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 3.00 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.2000, 0.4500, 0.3500]\n"
                "- Bằng chứng nguyên văn từ CV: \"Triển khai ứng dụng lên Kubernetes cluster...\"\n"
                "- Lịch sử hội thoại:\n"
                "- [Turn t=3, k=1, Skill='kubernetes', Slot='kubernetes:primary']\n"
                "  + Câu hỏi: Xử lý Pod bị OOMKilled exit code 137?\n"
                "  + Trả lời: Em kiểm tra heap dump và tăng limit memory trong Deployment spec.\n"
                "  + Judge Insight: Ứng viên biết cách khắc phục cơ bản. (Tag=MODERATE_SHIFT)"
            ),
            main_layer_directives=(
                "- Persona: SRE Lead.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH) tại lượt k=2.\n"
                "- Quản lý Probing Sub-slot: Sinh 1 sub-slot mới về Custom Metrics Autoscaling.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên biết tinh chỉnh thông số tĩnh trong Deployment nhưng chưa đề cập đến cơ chế tự động mở rộng (autoscaling) theo tải thực tế."
            ),
            hypothesis_A=(
                "Ứng viên có thể chỉ quen với CPU-based HPA mặc định mà chưa từng tích hợp Prometheus Adapter để scale Pod dựa trên độ dài hàng đợi tin nhắn."
            ),
            new_sub_slot=ProposedSubSlot(
                slot_name="custom_hpa",
                description="Tích hợp Custom Metrics Autoscaling (KEDA / Prometheus Adapter) cho workloads",
            ),
            target_slot_id="kubernetes:sub_1",
            question=(
                "Khi CPU của Pod không tăng nhưng hàng đợi tin nhắn của hệ thống bị ùn ứ, "
                "anh/chị tích hợp Horizontal Pod Autoscaler (HPA) với Prometheus hoặc KEDA như thế nào để tự động tăng số lượng Pod theo độ dài hàng đợi?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),

        # 20. PostgreSQL (k=2, PROBE_DEPTH - Probing Sub-slot 1)
        dspy.Example(
            reference_layer_context=(
                "- Kỹ năng mục tiêu (Primary Skill d*): `postgresql` (Matched CV Skill: `postgresql`)\n"
                "- Độ sâu năng lực yêu cầu từ JD (r_target = s_jd): 4.00 / 5.0\n"
                "- Điểm năng lực ước lượng ban đầu từ CV (s_cv): 2.80 / 5.0\n"
                "- Phân phối niềm tin hiện tại P_{t-1}: [0.2200, 0.4800, 0.3000]\n"
                "- Bằng chứng nguyên văn từ CV: \"Thiết kế cơ sở dữ liệu quan hệ PostgreSQL...\"\n"
                "- Ngữ cảnh công việc: Backend Developer\n"
                "- Lịch sử hội thoại:\n"
                "- [Turn t=4, k=1, Skill='postgresql', Slot='postgresql:primary']\n"
                "  + Câu hỏi: Dùng EXPLAIN ANALYZE tối ưu truy vấn chậm?\n"
                "  + Trả lời: Em phân tích cost, xem node nào bị seq scan thì thêm composite index.\n"
                "  + Judge Insight: Nắm vững nguyên lý đánh index cơ bản. (Tag=MODERATE_SHIFT)"
            ),
            main_layer_directives=(
                "- Persona: Database Administrator / Performance Lead.\n"
                "- Chiến lược phỏng vấn: Đào sâu chuyên môn (PROBE_DEPTH) tại lượt k=2.\n"
                "- Quản lý Probing Sub-slot: Sinh 1 sub-slot mới về giải quyết Deadlock đồng thời.\n"
                "- Ràng buộc: One-Question-One-Answer, Show Don't Tell."
            ),
            surprising_fact_C=(
                "Ứng viên tối ưu tốt truy vấn đọc (Read), nhưng chưa rõ cách xử lý xung đột khóa khi có nhiều giao dịch ghi (Write) đồng thời."
            ),
            hypothesis_A=(
                "Ứng viên có thể chưa từng trực tiếp giải quyết sự cố Deadlock giữa các transaction cập nhật dữ liệu đa luồng."
            ),
            new_sub_slot=ProposedSubSlot(
                slot_name="deadlock_resolution",
                description="Cơ chế phòng tránh và giải quyết Deadlock trong các giao dịch ghi đồng thời cao",
            ),
            target_slot_id="postgresql:sub_1",
            question=(
                "Khi nhiều giao dịch cùng cập nhật các bảng liên quan dẫn đến tình trạng Deadlock liên tục trong PostgreSQL, "
                "anh/chị dùng câu lệnh và phương pháp nào trong pg_locks để xác định chính xác chuỗi khóa gây nghẽn giữa các tiến trình?"
            ),
        ).with_inputs("reference_layer_context", "main_layer_directives"),
    ]

    if split == "train":
        return examples[:14]
    elif split in ("dev", "val"):
        return examples[14:]
    return examples


# ===========================================================================
# STEP 2B: REFLECTIVE PBA JUDGE GOLD EXAMPLES (20 CURATED SAMPLES)
# ===========================================================================

def get_gold_judge_examples(
    split: Literal["all", "train", "dev", "val"] = "all",
) -> List[dspy.Example]:
    """
    Curated few-shot demonstrations for Step 2B (Reflective PBA Metamorphic Judge).
    Covers all 4 Metamorphic Relations: INVARIANT, MINOR_SHIFT, MODERATE_SHIFT, DECISIVE_SHIFT (Low & High).
    Train: 14 examples | Dev: 6 examples | All: 20 examples.
    """
    examples = [
        # 1. DECISIVE_SHIFT -> Low (Java Spring)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `java_spring`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.30 / 5.0\n"
                "- Bằng chứng trong CV: \"Phát triển các RESTful API CRUD cơ bản...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3925, 0.4126, 0.1949]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `java_spring:primary`\n"
                "- Câu hỏi: \"Khi một phương thức @Transactional gặp RuntimeException, anh/chị cấu hình rollback và propagation như thế nào?\""
            ),
            candidate_response=(
                "Thực tế em mới chỉ dùng Spring Boot để viết các API CRUD cơ bản và gọi hàm có sẵn của Spring Data JPA, "
                "chứ chưa từng trực tiếp xử lý các vấn đề chuyên sâu về quản lý Transaction phức tạp hay cấu hình propagation."
            ),
            extracted_slot_value="Chưa từng trực tiếp xử lý các vấn đề chuyên sâu về quản lý Transaction phức tạp; chỉ mới dùng Spring Boot viết API CRUD cơ bản.",
            reflective_insight=(
                "Ứng viên thừa nhận rõ ràng chỉ làm việc ở mức CRUD cơ bản và thiếu kinh nghiệm xử lý transaction trong production, "
                "khớp hoàn toàn với tiêu chí Low (1.5) về việc chưa hiểu cơ chế bên dưới."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.85, 0.10, 0.05],
            consolidated_summary="Ứng viên thừa nhận chỉ có kinh nghiệm CRUD cơ bản và thiếu kỹ năng xử lý transaction phức tạp trong production, xác nhận mức năng lực Low.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 2. MODERATE_SHIFT -> Med (Terraform)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `terraform`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.40 / 5.0\n"
                "- Bằng chứng trong CV: \"Tự động hóa cấp phát hạ tầng AWS bằng CloudFormation templates.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3689, 0.4286, 0.2024]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `terraform:primary`\n"
                "- Câu hỏi: \"Anh/chị thiết kế cơ chế Remote Backend kết hợp State Locking như thế nào để ngăn chặn xung đột?\""
            ),
            candidate_response=(
                "Em dùng S3 bucket để lưu tfstate và bật versioning, sau đó cấu hình DynamoDB table làm lock table. "
                "Mỗi khi ai đó chạy terraform apply thì sẽ lấy lock từ DynamoDB trước, nếu có người đang chạy thì sẽ báo lỗi chờ."
            ),
            extracted_slot_value="Cấu hình Terraform backend dùng S3 (bật versioning) kết hợp DynamoDB table cho State Locking khi chạy terraform apply.",
            reflective_insight=(
                "Ứng viên nắm vững cơ chế remote backend chuẩn với S3 và DynamoDB locking, đáp ứng tốt yêu cầu vận hành độc lập ở mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên nắm vững và triển khai thành thạo mô hình Remote State S3 kết hợp DynamoDB Locking cho Terraform, đạt mức năng lực Med.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 3. INVARIANT (Docker)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `docker`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 3.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.50 / 5.0\n"
                "- Bằng chứng trong CV: \"Sử dụng Docker đóng gói ứng dụng.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3460, 0.4442, 0.2098]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `docker:primary`\n"
                "- Câu hỏi: \"Anh/chị đã áp dụng những kỹ thuật nào trong Dockerfile để tối ưu hóa kích thước image và tăng tốc độ build?\""
            ),
            candidate_response=(
                "Dạ em dùng Docker rất nhiều, Docker là công nghệ ảo hóa rất tốt giúp đóng gói ứng dụng nhanh chóng, "
                "triển khai CI/CD rất mượt mà và hiện đại cho toàn bộ team."
            ),
            extracted_slot_value=None,
            reflective_insight=(
                "Câu trả lời hoàn toàn là buzzwords chung chung, không đưa ra được bất kỳ kỹ thuật cụ thể nào (như multi-stage build, .dockerignore hay tối ưu layer cache)."
            ),
            metamorphic_tag=MetamorphicTag.INVARIANT,
            raw_posterior_probs=[0.3460, 0.4442, 0.2098],
            consolidated_summary="Ứng viên trả lời chung chung mang tính quảng bá khái niệm, chưa cung cấp được bằng chứng kỹ thuật cụ thể về tối ưu Docker image.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 4. MINOR_SHIFT (AWS - Context Invalidation / Organizational Constraint)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `aws`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.70 / 5.0\n"
                "- Bằng chứng trong CV: \"Sử dụng EC2, S3 và RDS để vận hành ứng dụng trên AWS.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3021, 0.4745, 0.2234]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `aws:primary`\n"
                "- Câu hỏi: \"Anh/chị cấu hình cơ chế Multi-AZ failover giữa Application Load Balancer và RDS như thế nào?\""
            ),
            candidate_response=(
                "Ở công ty cũ của em, toàn bộ phần thiết lập mạng VPC và Multi-AZ do đội DevOps chuyên trách quản lý. "
                "Em là developer chỉ được cấp quyền đọc CloudWatch để xem log và cấu hình biến môi trường kết nối database thôi ạ."
            ),
            extracted_slot_value="Bị giới hạn phân quyền tổ chức; chỉ có quyền đọc CloudWatch và cấu hình kết nối, chưa trực tiếp cấu hình Multi-AZ hay ALB.",
            reflective_insight=(
                "Ứng viên đưa ra rào cản phân quyền tổ chức hợp lệ (Context Invalidation). Bằng chứng gián tiếp cho thấy hiểu mục đích nhưng chưa từng trực tiếp thực thi, gán MINOR_SHIFT."
            ),
            metamorphic_tag=MetamorphicTag.MINOR_SHIFT,
            raw_posterior_probs=[0.4200, 0.4500, 0.1300],
            consolidated_summary="Ứng viên hiểu vai trò của dịch vụ AWS nhưng bị giới hạn phân quyền thực thi hạ tầng mạng thực tế, dịch chuyển nhẹ niềm tin sang phân khúc cơ bản.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 5. DECISIVE_SHIFT -> High (Kubernetes Expert Troubleshooting)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `kubernetes`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 3.00 / 5.0\n"
                "- Bằng chứng trong CV: \"Triển khai ứng dụng lên Kubernetes cluster bằng Helm chart.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2429, 0.5142, 0.2429]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `kubernetes:primary`\n"
                "- Câu hỏi: \"Khi Pod liên tục bị OOMKilled exit code 137, anh/chị điều tra và cấu hình lại resource limits ra sao?\""
            ),
            candidate_response=(
                "Đầu tiên em dùng kubectl describe pod để xác định container bị OOMKilled. Tiếp theo em chụp heap dump của JVM "
                "bằng cách cấu hình flag -XX:+HeapDumpOnOutOfMemoryError lưu vào persistent volume. Sau khi phân tích thấy ứng dụng Java "
                "không nhận diện được cgroup v2 của K8s dẫn đến phân bổ quá RAM máy ảo, em đã cấu hình lại cgroup v2 và thêm flag "
                "-XX:MaxRAMPercentage=75.0, đồng thời căn chỉnh memory request bằng 80% limit để container luôn đạt Guaranteed QoS Class."
            ),
            extracted_slot_value="Phân tích heap dump JVM, giải quyết lỗi nhận diện cgroup v2, cấu hình -XX:MaxRAMPercentage=75.0 và căn chỉnh Guaranteed QoS Class.",
            reflective_insight=(
                "Ứng viên phân tích tường tận nguyên nhân gốc từ cgroup v2 đến JVM container ergonomics và QoS class, thể hiện năng lực chuyên gia production High (4.5)."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.05, 0.15, 0.80],
            consolidated_summary="Ứng viên thể hiện trình độ chuyên gia vượt trội trong xử lý sự cố OOMKilled và tối ưu container runtime, xác nhận mức High.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 6. MODERATE_SHIFT -> Med (PostgreSQL EXPLAIN ANALYZE)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `postgresql`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.80 / 5.0\n"
                "- Bằng chứng trong CV: \"Thiết kế cơ sở dữ liệu quan hệ PostgreSQL...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2810, 0.4855, 0.2335]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `postgresql:primary`\n"
                "- Câu hỏi: \"Anh/chị dùng EXPLAIN ANALYZE đọc các chỉ số then chốt nào nhằm quyết định chiến lược đánh chỉ mục?\""
            ),
            candidate_response=(
                "Em kiểm tra node nào có Seq Scan và so sánh cost ước tính với actual time. Nếu số rows thực tế lệch lớn với estimated rows "
                "thì em chạy ANALYZE lại bảng. Nếu câu lệnh lọc theo nhiều điều kiện WHERE kết hợp ORDER BY thì em tạo composite B-tree index "
                "theo quy tắc cột có tính chọn lọc cao đứng trước."
            ),
            extracted_slot_value="Nhận diện Seq Scan, đối chiếu actual time với cost, chạy ANALYZE cập nhật thống kê, tạo composite B-tree index theo quy tắc độ chọn lọc.",
            reflective_insight=(
                "Ứng viên nắm vững quy trình tuning thực tế bằng EXPLAIN ANALYZE và nguyên lý composite index, đạt mức Med (3.0) vững chắc."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên nắm vững và vận dụng chuẩn xác kỹ thuật phân tích Execution Plan và tối ưu composite index trong PostgreSQL.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 7. INVARIANT (Security - Verbatim CV Repetition)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `microservices_security`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.50 / 5.0\n"
                "- Bằng chứng trong CV: \"Xác thực người dùng bằng JSON Web Token (JWT).\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3460, 0.4442, 0.2098]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `microservices_security:primary`\n"
                "- Câu hỏi: \"Anh/chị thiết kế giải pháp thu hồi quyền truy cập (Token Revocation) tức thời ở API Gateway như thế nào?\""
            ),
            candidate_response=(
                "Dạ như trong CV em có ghi, em làm bảo mật theo chuẩn công ty và dùng JWT để xác thực người dùng trong các API microservices."
            ),
            extracted_slot_value=None,
            reflective_insight=(
                "Ứng viên chỉ nhắc lại nguyên văn nội dung trong CV, hoàn toàn né tránh câu hỏi kỹ thuật về thu hồi token, gán INVARIANT."
            ),
            metamorphic_tag=MetamorphicTag.INVARIANT,
            raw_posterior_probs=[0.3460, 0.4442, 0.2098],
            consolidated_summary="Ứng viên lặp lại thông tin CV và né tránh giải pháp kỹ thuật, giữ nguyên phân phối niềm tin ban đầu.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 8. DECISIVE_SHIFT -> High (Kafka Deep Production Mastery)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `kafka`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.50 / 5.0\n"
                "- Bằng chứng trong CV: \"Sử dụng RabbitMQ để xử lý hàng đợi tin nhắn...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3460, 0.4442, 0.2098]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `kafka:primary`\n"
                "- Câu hỏi: \"Anh/chị phân tích nguyên nhân và điều chỉnh cơ chế tiêu thụ tin nhắn trong Consumer Group như thế nào để giải tỏa tắc nghẽn?\""
            ),
            candidate_response=(
                "Khi lag tăng đột biến, em kiểm tra xem có hiện tượng rebalancing storm không. Trong hệ thống trước đây, do xử lý tin nhắn quá lâu "
                "khiến quá thời gian max.poll.interval.ms làm coordinator tưởng consumer chết và rebalance liên tục. Em đã chuyển sang dùng "
                "CooperativeStickyAssignor để rebalance tăng dần không dừng toàn bộ consumer, đồng thời bóc tách tác vụ I/O nặng sang worker pool riêng "
                "và commit offset thủ công theo batch sau khi hoàn thành."
            ),
            extracted_slot_value="Phát hiện rebalancing storm do quá max.poll.interval.ms; áp dụng CooperativeStickyAssignor, tách async worker pool và commit offset theo batch.",
            reflective_insight=(
                "Ứng viên hiểu sâu sắc về coordinator protocol, Cooperative Sticky Assignor và quản lý offset ở mức production quy mô lớn, đạt High (4.5)."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.05, 0.15, 0.80],
            consolidated_summary="Ứng viên thể hiện hiểu biết sâu sắc về kiến trúc nội tại Kafka và giải quyết sự cố rebalancing phức tạp, xác nhận mức High.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 9. MINOR_SHIFT (Golang Concurrency Basics)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `golang`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.60 / 5.0\n"
                "- Bằng chứng trong CV: \"Phát triển microservice xử lý dữ liệu bằng Go.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3235, 0.4608, 0.2157]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `golang:primary`\n"
                "- Câu hỏi: \"Anh/chị sử dụng công cụ hoặc mẫu thiết kế nào để phát hiện và kiểm soát việc rò rỉ goroutine?\""
            ),
            candidate_response=(
                "Em dùng sync.WaitGroup để đợi các goroutine kết thúc trước khi hàm main return, "
                "còn công cụ chuyên dụng để đo rò rỉ bộ nhớ thì dự án trước em chưa cấu hình profiling trực tiếp."
            ),
            extracted_slot_value="Sử dụng sync.WaitGroup cơ bản để chờ goroutine; chưa từng cấu hình pprof hay công cụ profiling rò rỉ goroutine.",
            reflective_insight=(
                "Ứng viên nắm được cú pháp đồng bộ cơ bản nhưng chưa có kinh nghiệm phát hiện goroutine leak qua runtime profiling, gán MINOR_SHIFT."
            ),
            metamorphic_tag=MetamorphicTag.MINOR_SHIFT,
            raw_posterior_probs=[0.4500, 0.4500, 0.1000],
            consolidated_summary="Ứng viên nắm cú pháp concurrency cơ bản trong Go nhưng chưa có kỹ năng profiling xử lý rò rỉ luồng trong môi trường thực chiến.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 10. MODERATE_SHIFT -> Med (Redis Cache Stampede)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `redis`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 3.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.20 / 5.0\n"
                "- Bằng chứng trong CV: \"Sử dụng Memcached để lưu tạm session...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.4182, 0.3956, 0.1862]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `redis:primary`\n"
                "- Câu hỏi: \"Anh/chị thiết kế giải pháp như thế nào để ngăn chặn hiện tượng Cache Stampede khi key có lượng truy cập lớn hết hạn?\""
            ),
            candidate_response=(
                "Em áp dụng hai giải pháp: thứ nhất là thêm một khoảng thời gian jitter ngẫu nhiên vào TTL của key để các key không hết hạn cùng lúc; "
                "thứ hai là khi key hết hạn, dùng Redis Distributed Lock (SETNX) để chỉ cho phép một worker chạy query database cập nhật cache, "
                "các request khác chờ hoặc nhận dữ liệu cũ tạm thời."
            ),
            extracted_slot_value="Thêm jitter ngẫu nhiên vào TTL và sử dụng Distributed Lock (SETNX) để chỉ 1 request truy vấn DB làm mới cache.",
            reflective_insight=(
                "Ứng viên đưa ra các giải pháp chuẩn mực trong ngành (Jitter TTL và SETNX Mutex), đáp ứng tốt năng lực độc lập ở mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên giải quyết tốt bài toán Cache Stampede bằng các giải thuật phân tán chuẩn trong Redis, đạt mức Med.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 11. DECISIVE_SHIFT -> Low (Elasticsearch Admission)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `elasticsearch`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 3.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.00 / 5.0\n"
                "- Bằng chứng trong CV: \"Tìm kiếm dữ liệu toàn văn bằng tính năng Full-text search của PostgreSQL.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.4658, 0.3628, 0.1714]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `elasticsearch:primary`\n"
                "- Câu hỏi: \"Anh/chị lựa chọn bộ Analyzer và cấu hình Tokenizer ra sao để tìm kiếm chính xác các cụm từ kỹ thuật?\""
            ),
            candidate_response=(
                "Thành thật là em chưa từng trực tiếp cấu hình Analyzer hay mapping trong Elasticsearch bao giờ. "
                "Em mới chỉ đọc qua tài liệu khái niệm thôi chứ chưa triển khai vào dự án thực tế."
            ),
            extracted_slot_value="Thừa nhận chưa từng trực tiếp cấu hình Analyzer, mapping hay triển khai Elasticsearch trong dự án thực tế.",
            reflective_insight=(
                "Ứng viên thừa nhận rõ ràng việc chưa từng làm việc thực tế với Elasticsearch, xác nhận dứt khoát mức năng lực Low (1.5)."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.85, 0.10, 0.05],
            consolidated_summary="Ứng viên thẳng thắn thừa nhận thiếu kinh nghiệm thực tế với Elasticsearch, xác nhận mức năng lực Low.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 12. MODERATE_SHIFT -> Med (GitLab CI Caching)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `ci_cd`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 3.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.40 / 5.0\n"
                "- Bằng chứng trong CV: \"Cấu hình Jenkins job để tự động build và deploy...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3689, 0.4286, 0.2024]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `ci_cd:primary`\n"
                "- Câu hỏi: \"Anh/chị cấu hình cơ chế caching dependencies giữa các job như thế nào để rút ngắn thời gian pipeline?\""
            ),
            candidate_response=(
                "Trong file .gitlab-ci.yml, em định nghĩa block cache với key dựa theo hash của file package-lock.json hoặc build.gradle. "
                "Khi lockfile không đổi thì GitLab Runner sẽ kéo cache về thay vì tải lại toàn bộ dependencies, giúp giảm thời gian build từ 12 phút xuống còn 3 phút."
            ),
            extracted_slot_value="Cấu hình cache key theo hash của lockfile trong .gitlab-ci.yml, giảm thời gian build từ 12 phút xuống 3 phút.",
            reflective_insight=(
                "Ứng viên giải thích cụ thể cơ chế cache key theo checksum file dependency và đưa ra kết quả đo lường thời gian thực tế, đạt mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên hiểu rõ và áp dụng thành công kỹ thuật caching tối ưu hiệu năng pipeline trong GitLab CI, đạt mức Med.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 13. MODERATE_SHIFT -> Med (ReactJS Profiler Optimization)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `reactjs`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.50 / 5.0\n"
                "- Bằng chứng trong CV: \"Xây dựng giao diện người dùng web sử dụng ReactJS và Redux.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3460, 0.4442, 0.2098]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `reactjs:primary`\n"
                "- Câu hỏi: \"Anh/chị dùng React DevTools Profiler như thế nào để khoanh vùng nguyên nhân và tối ưu hóa việc truyền props?\""
            ),
            candidate_response=(
                "Em bật tùy chọn 'Highlight updates when components render' và ghi lại phiên thao tác bằng Profiler để tìm component có render time dài. "
                "Em phát hiện nguyên nhân là do truyền inline arrow function làm thay đổi prop reference ở mỗi lần render, "
                "nên em đã bọc các callback đó bằng useCallback và dùng React.memo cho component con."
            ),
            extracted_slot_value="Sử dụng React Profiler phát hiện đổi reference do inline function; áp dụng useCallback và React.memo để chặn re-render thừa.",
            reflective_insight=(
                "Ứng viên sử dụng thành thạo công cụ profiling để giải quyết vấn đề prop reference gây render thừa, đạt mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên có kỹ năng thực tế vững vàng về profiling và tối ưu hóa chu kỳ render trong ReactJS.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 14. MINOR_SHIFT (Kafka Basic Lag Approach)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `kafka`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.50 / 5.0\n"
                "- Bằng chứng trong CV: \"Sử dụng RabbitMQ để xử lý hàng đợi tin nhắn...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3460, 0.4442, 0.2098]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `kafka:primary`\n"
                "- Câu hỏi: \"Anh/chị phân tích nguyên nhân và điều chỉnh cơ chế tiêu thụ tin nhắn trong Consumer Group như thế nào để giải tỏa tắc nghẽn?\""
            ),
            candidate_response=(
                "Mỗi khi thấy tin nhắn bị chậm thì bên em vào xem bảng điều khiển Kafka UI, thấy lag tăng thì team em restart lại service consumer "
                "hoặc tăng tạm thêm RAM cho pod để nó tiêu thụ nhanh hơn."
            ),
            extracted_slot_value="Xem giao diện Kafka UI; xử lý lag bằng cách restart service consumer hoặc tăng RAM cho pod tạm thời.",
            reflective_insight=(
                "Ứng viên có tiếp xúc với Kafka nhưng giải pháp mang tính đối phó thủ công (restart pod), chưa chạm tới bản chất partition và consumer offset, gán MINOR_SHIFT."
            ),
            metamorphic_tag=MetamorphicTag.MINOR_SHIFT,
            raw_posterior_probs=[0.4500, 0.4500, 0.1000],
            consolidated_summary="Ứng viên nhận biết được sự cố lag nhưng giải pháp mang tính đối phó thụ động, phản ánh mức năng lực cơ bản.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # ===================================================================
        # DEV / EVALUATION SPLIT (EXAMPLES 15 - 20)
        # ===================================================================

        # 15. DECISIVE_SHIFT -> High (PostgreSQL Deadlock Concurrency Mastery)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `postgresql`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.80 / 5.0\n"
                "- Bằng chứng trong CV: \"Thiết kế cơ sở dữ liệu quan hệ PostgreSQL...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2810, 0.4855, 0.2335]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `postgresql:sub_1`\n"
                "- Câu hỏi: \"Anh/chị xác định chuỗi khóa gây nghẽn và chuẩn hóa thứ tự giao dịch để loại trừ Deadlock như thế nào?\""
            ),
            candidate_response=(
                "Em dùng view pg_stat_activity kết hợp pg_locks để tìm các pid đang bị blocked và chuỗi lock dependency. "
                "Nguyên nhân deadlock cốt lõi thường là do 2 giao dịch cập nhật các dòng theo thứ tự ngược nhau (Transaction A cập nhật user rồi order, "
                "Transaction B ngược lại). Em đã chuẩn hóa toàn bộ mã nguồn phải lock theo thứ tự ID tăng dần, đồng thời thiết lập lock_timeout=3s "
                "và chuyển các tác vụ cập nhật số dư sang dùng Optimistic Locking với cột version để tránh giữ pessimistic lock lâu."
            ),
            extracted_slot_value="Truy vấn pg_locks/pg_stat_activity, chuẩn hóa thứ tự lock theo ID tăng dần, thiết lập lock_timeout=3s và áp dụng Optimistic Locking với version column.",
            reflective_insight=(
                "Ứng viên phân tích chuẩn xác cơ chế lock dependency và giải quyết deadlock bằng các phương pháp kiến trúc chuyên sâu, đạt High (4.5)."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.05, 0.15, 0.80],
            consolidated_summary="Ứng viên thể hiện trình độ chuyên gia về cơ chế khóa và xử lý xung đột đồng thời cao trong PostgreSQL, xác nhận mức High.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 16. DECISIVE_SHIFT -> Low (System Design Distributed Rate Limiting Admission)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `system_design`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.80 / 5.0\n"
                "- Bằng chứng trong CV: \"Tham gia thiết kế kiến trúc các dịch vụ backend...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2810, 0.4855, 0.2335]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `system_design:primary`\n"
                "- Câu hỏi: \"Anh/chị thiết kế cơ chế Rate Limiting phân tán sử dụng Redis với thuật toán cụ thể nào?\""
            ),
            candidate_response=(
                "Về phần Rate Limiting này ở công ty em dùng Cloudflare để chặn IP ở tầng ngoài thôi chứ ở tầng backend "
                "thì em chưa từng tự tay thiết kế thuật toán hay dùng Redis để giới hạn request phân tán bao giờ ạ."
            ),
            extracted_slot_value="Thừa nhận chưa từng thiết kế thuật toán Rate Limiting phân tán hay cấu hình Redis giới hạn request ở tầng backend.",
            reflective_insight=(
                "Ứng viên thẳng thắn thừa nhận chưa từng thiết kế rate limiting phân tán, không đạt yêu cầu chuyên sâu 4.5 của JD, xác nhận Low (1.5)."
            ),
            metamorphic_tag=MetamorphicTag.DECISIVE_SHIFT,
            raw_posterior_probs=[0.85, 0.10, 0.05],
            consolidated_summary="Ứng viên thừa nhận chưa có kinh nghiệm thiết kế thuật toán bảo vệ hệ thống tải cao, xác nhận mức năng lực Low.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 17. INVARIANT (PostgreSQL - Off-topic response)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `postgresql`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.80 / 5.0\n"
                "- Bằng chứng trong CV: \"Thiết kế cơ sở dữ liệu quan hệ PostgreSQL...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2810, 0.4855, 0.2335]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `postgresql:primary`\n"
                "- Câu hỏi: \"Anh/chị dùng EXPLAIN ANALYZE đọc các chỉ số then chốt nào nhằm quyết định chiến lược đánh chỉ mục?\""
            ),
            candidate_response=(
                "Dạ em rất đam mê công nghệ dữ liệu, em thấy PostgreSQL là database mã nguồn mở tốt nhất hiện nay và em thường xuyên đọc các bài viết về database."
            ),
            extracted_slot_value=None,
            reflective_insight=(
                "Câu trả lời hoàn toàn mang tính cảm nghĩ cá nhân, lạc đề và không chứa bất kỳ phân tích kỹ thuật nào liên quan đến EXPLAIN ANALYZE."
            ),
            metamorphic_tag=MetamorphicTag.INVARIANT,
            raw_posterior_probs=[0.2810, 0.4855, 0.2335],
            consolidated_summary="Ứng viên trả lời lạc đề và né tránh câu hỏi kỹ thuật chuyên sâu, giữ nguyên trạng thái niềm tin.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 18. MINOR_SHIFT (Kubernetes Template-based Operation)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `kubernetes`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.50 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 3.00 / 5.0\n"
                "- Bằng chứng trong CV: \"Triển khai ứng dụng lên Kubernetes cluster bằng Helm chart.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.2429, 0.5142, 0.2429]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `kubernetes:primary`\n"
                "- Câu hỏi: \"Khi Pod liên tục bị OOMKilled exit code 137, anh/chị điều tra và cấu hình lại resource limits ra sao?\""
            ),
            candidate_response=(
                "Em dùng kubectl logs xem pod có báo lỗi gì không, sau đó em mở file helm values.yaml do Tech Lead viết sẵn "
                "rồi tăng thông số memory limit lên gấp đôi rồi chạy lệnh helm upgrade để deploy lại."
            ),
            extracted_slot_value="Xem kubectl logs, chỉnh sửa file values.yaml có sẵn bằng cách tăng gấp đôi memory limit và chạy helm upgrade.",
            reflective_insight=(
                "Ứng viên biết vận hành theo mẫu có sẵn nhưng thiếu phương pháp điều tra nguyên nhân rò rỉ bộ nhớ thực sự, gán MINOR_SHIFT."
            ),
            metamorphic_tag=MetamorphicTag.MINOR_SHIFT,
            raw_posterior_probs=[0.3500, 0.5500, 0.1000],
            consolidated_summary="Ứng viên thao tác dựa trên cấu hình mẫu sẵn có, chưa làm chủ phương pháp điều tra lỗi tài nguyên sâu trong container.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 19. MODERATE_SHIFT -> Med (Spring Boot Propagation)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `java_spring`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.30 / 5.0\n"
                "- Bằng chứng trong CV: \"Phát triển các RESTful API CRUD cơ bản...\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3925, 0.4126, 0.1949]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `java_spring:primary`\n"
                "- Câu hỏi: \"Anh/chị cấu hình cơ chế rollback và quản lý propagation như thế nào để đảm bảo tính toàn vẹn dữ liệu?\""
            ),
            candidate_response=(
                "Em khai báo @Transactional(rollbackFor = Exception.class) ở tầng Service. Trong trường hợp cần gọi sang một service ghi log "
                "độc lập mà không muốn bị rollback theo transaction chính nếu có lỗi, em cấu hình method đó với Propagation.REQUIRES_NEW để mở transaction riêng."
            ),
            extracted_slot_value="Áp dụng @Transactional(rollbackFor = Exception.class) và sử dụng Propagation.REQUIRES_NEW cho transaction ghi log độc lập.",
            reflective_insight=(
                "Ứng viên giải thích chuẩn xác sự khác biệt giữa rollback mặc định của Spring và ứng dụng Propagation.REQUIRES_NEW, đạt mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên nắm vững cơ chế Transaction Propagation và xử lý rollback trong Spring Boot, đạt mức Med.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),

        # 20. MODERATE_SHIFT -> Med (GraphQL DataLoader)
        dspy.Example(
            reference_layer_rubric=(
                "- Kỹ năng đang đánh giá (d*): `graphql`\n"
                "- Mức năng lực yêu cầu từ JD (s_jd): 4.00 / 5.0\n"
                "- Mức năng lực ước lượng từ CV (s_cv): 2.40 / 5.0\n"
                "- Bằng chứng trong CV: \"Xây dựng hệ thống REST API theo chuẩn OpenAPI.\"\n"
                "- Hệ quy chiếu Rubric: Low(1.5), Med(3.0), High(4.5)\n"
                "- Phân phối niềm tin liền trước P_{t-1}: [0.3689, 0.4286, 0.2024]"
            ),
            question_and_slot=(
                "- Slot mục tiêu: `graphql:primary`\n"
                "- Câu hỏi: \"Làm thế nào anh/chị áp dụng cơ chế Batching và Caching của DataLoader để giải quyết triệt để N+1 query?\""
            ),
            candidate_response=(
                "Khi nhiều field resolver cùng cần lấy thông tin tác giả của danh sách bài viết, thay vì mỗi resolver gửi một câu SELECT độc lập, "
                "DataLoader sẽ gom toàn bộ author_id trong cùng một tick của Event Loop thành một mảng rồi gửi duy nhất một câu lệnh WHERE id IN (...) "
                "xuống database, sau đó phân phối lại kết quả theo thứ tự."
            ),
            extracted_slot_value="DataLoader gom mảng IDs trong cùng một tick của Event Loop thành câu truy vấn WHERE id IN (...), phân phối kết quả về đúng resolver.",
            reflective_insight=(
                "Ứng viên hiểu rõ cơ chế batching dựa trên Event Loop tick của DataLoader để triệt tiêu vấn đề N+1 query, đạt mức Med (3.0)."
            ),
            metamorphic_tag=MetamorphicTag.MODERATE_SHIFT,
            raw_posterior_probs=[0.10, 0.75, 0.15],
            consolidated_summary="Ứng viên hiểu rõ nguyên lý hoạt động của DataLoader trong giải quyết truy vấn N+1 của GraphQL, đạt mức Med.",
        ).with_inputs("reference_layer_rubric", "question_and_slot", "candidate_response"),
    ]

    if split == "train":
        return examples[:14]
    elif split in ("dev", "val"):
        return examples[14:]
    return examples
