# Dữ liệu phỏng vấn bàn giao cho module ôn luyện

Đối chiếu code ngày 09/11/2026. Tài liệu mô tả luồng evidence V2 và hồ sơ ứng tuyển hiện tại; không áp dụng trực tiếp cho snapshot của engine cũ. Lần bàn giao này chỉ cập nhật tài liệu, không bổ sung entity, migration, API hoặc thay đổi thuật toán.

## 0. Người làm ôn luyện bắt đầu từ đâu?

### Trách nhiệm của hai phần

Phần phỏng vấn cung cấp yêu cầu cần đạt, câu trả lời gốc, bằng chứng, kết luận từng phiên và kết quả tổng hợp năng lực hiện tại. Phần ôn luyện sử dụng dữ liệu đó để xây kế hoạch, nội dung học, bài tập, tài liệu, checklist, ghi chú và tiến độ do người dùng ghi nhận.

Đối tượng liên kết là **hồ sơ ứng tuyển với một bộ CV/JD**, không chỉ user hoặc tên kỹ năng. Cùng một người có thể có nhiều hồ sơ với mức yêu cầu khác nhau.

### Ba loại dữ liệu phải phân biệt

| Dữ liệu | Lấy ở đâu? | Có lưu trong database không? | Dùng cho ôn luyện |
|---|---|---|---|
| Gap dự đoán từ CV/JD | `application_profiles.skill_gap_json` | Có, JSON trong cột TEXT | Biết xuất phát điểm và yêu cầu JD. Chưa xác nhận người dùng yếu. |
| Bằng chứng và kết luận từng phiên | `interview_runs.snapshot_json`; bản rút gọn tại `public_json` | Có, backend lưu sau mỗi chuyển trạng thái thành công | Biết đã kiểm tra gì, biểu hiện nào đã quan sát và nguồn kết luận. |
| Năng lực hiện tại qua các lượt | `ApplicationCompetencyService.get(profileId, user)` / API competency | Chưa lưu kết quả thành entity riêng; được tính từ lịch sử trong DB khi đọc | Quyết định nội dung hiện còn cần ưu tiên, đã đạt hay cần xác minh. |

Không ghi đè `candidate_proficiency` hoặc `gap_magnitude` ban đầu bằng kết quả phỏng vấn. Hiện chưa có field số `verified_gap_magnitude`; năng lực quan sát được thể hiện bằng assessment và bằng chứng.

### Bộ thông tin tối thiểu cần sử dụng

| Nhu cầu của ôn luyện | Dữ liệu cần lấy | Nguồn hiện tại |
|---|---|---|
| Gắn đầu việc với đúng nội dung | Profile ID, skill ID, objective ID, criterion ID, rubric fingerprint | SQL của hồ sơ, blueprint và projection; xem mục 1, 3, 6. |
| Biết cần đạt gì | Claim, mô tả tiêu chí, at_target, expected_evidence, target_depth | Blueprint của hồ sơ. |
| Biết tình trạng hiện tại | Assessment ở cấp skill/objective/criterion, explanation, lastAssessment | CompetencyProjection. Không trộn kết luận giữa các cấp. |
| Biết vì sao đề xuất học | Rationale, trích đoạn trả lời, câu hỏi, depth, assistance, independent | Snapshot của các phiên liên quan. |
| Biết còn chưa rõ điều gì | Unresolved aspects, contradictions, stop reason | Snapshot; đối chiếu kết quả tổng hợp để tránh dùng thông tin cũ đã được giải quyết. |
| Sắp xếp ưu tiên | Importance weight, requirement kind và trạng thái hiện tại | Phân tích ban đầu + blueprint + projection. Priority ban đầu chưa tự cập nhật theo tiến bộ. |
| Truy vết kết luận | Session ID, turn ID, attempt number, rubric/policy version | Snapshot, bảng sessions và source trong projection. |

Các tên trong cột nhu cầu là ý nghĩa nghiệp vụ; field JSON chính xác được liệt kê ở các mục bên dưới. Dữ liệu snapshot dùng snake_case; đầu ra Java của competency dùng camelCase và một số field tên `id`.

### Trình tự tích hợp với code hiện tại

1. Chọn hồ sơ và kiểm tra người dùng là chủ sở hữu.
2. Đọc baseline và blueprint của hồ sơ để xác định chuẩn, khóa liên kết và tầm quan trọng.
3. Lấy năng lực hiện tại qua `ApplicationCompetencyService` hoặc API competency có sẵn.
4. Ghép `skills[].skillId` với `objective.skill_id`; ghép `objectives[].id` với `objective_id`; ghép `criteria[].id` với `criterion_id`. Kiểm tra rubric tương thích khi lấy chi tiết từ phiên nguồn.
5. Dựa vào kết luận mục tiêu và tiêu chí liên quan để chọn nội dung ôn. Nếu cần giải thích hoặc tạo bài luyện, đọc snapshot của phiên nguồn; không chỉ dựa vào một câu study_recommendations.
6. Lưu đầu việc/ghi chú/checklist trong dữ liệu của module ôn luyện, kèm các khóa nguồn cần thiết. Khi đọc lại kế hoạch sau một lượt phỏng vấn mới, đối chiếu kết luận tổng hợp mới; không tự đánh dấu hoàn thành đầu việc.

Nếu chỉ truy vấn SQL, hiện lấy được toàn bộ dữ liệu gốc nhưng **không có sẵn bảng năng lực hiện tại để SELECT**. Cần tái sử dụng bộ tổng hợp qua backend/service. Nếu hai bên muốn chỉ đọc kết quả tổng hợp từ DB, phải triển khai thêm entity lưu kết quả; đây là phương án đã thảo luận, chưa được triển khai trong hiện trạng bàn giao.

API đang có:

| API | Nội dung dùng được |
|---|---|
| `GET /api/v1/application-profiles/{id}` | Metadata hồ sơ, baseline tại `skills`, báo cáo ban đầu tại `analysis`, danh sách `attempts`. Response hiện không chứa blueprint đầy đủ. |
| `GET /api/v1/application-profiles/{id}/competency` | Năng lực tổng hợp qua các lượt. |
| `GET /api/v2/sessions/{sessionId}/interview` | Public state gồm turns và report, không phải snapshot nội bộ đầy đủ. |
| `GET /api/v2/sessions/{sessionId}/interview/report` | Báo cáo rút gọn của một phiên. |

Các API trên yêu cầu xác thực và kiểm tra quyền. Blueprint đầy đủ và chi tiết chẩn đoán ngoài public report hiện cần đọc qua backend/DB; chưa có API bàn giao mới trong tài liệu này.

## 1. Phạm vi và vị trí lưu

Dữ liệu hiện có đủ làm đầu vào cho kế hoạch tự ôn tập: biết yêu cầu cần đạt, biểu hiện đã quan sát, bằng chứng, phần chưa rõ và kết luận qua các lượt. Bài học, tài liệu, checklist và thao tác hoàn thành thuộc module ôn luyện.

Các cột JSON dưới đây hiện là PostgreSQL TEXT, cần parse JSON trong backend hoặc cast khi truy vấn. Các đường dẫn bên trong JSON không phải cột SQL riêng.

| Bảng / cột | Nội dung |
|---|---|
| `application_profiles.id`, `user_id` | Hồ sơ CV/JD và chủ sở hữu. Đọc dữ liệu phải kiểm tra quyền của người dùng. |
| `application_profiles.cv_text`, `jd_text` | Bản chụp tài liệu của hồ sơ. |
| `application_profiles.skill_gap_json` | Mảng phân tích CV/JD ban đầu, chưa phải năng lực được kiểm chứng. |
| `application_profiles.gap_report_json` | Báo cáo phân tích tài liệu ban đầu. |
| `application_profiles.blueprint_json` | Bộ mục tiêu và tiêu chí chung; được lưu khi bắt đầu lượt đầu. Có thể null trước đó. |
| `application_profiles.policy_json` | Chính sách đánh giá được cố định cùng blueprint. |
| `sessions.id`, `application_profile_id`, `attempt_number` | Liên kết phiên với hồ sơ và số thứ tự lượt. Phiên cũ có thể không thuộc hồ sơ. |
| `sessions.status`, `started_at`, `ended_at` | Trạng thái và thời gian của lượt. Dùng snapshot để xác nhận phiên đã kết thúc; status Completed không có nghĩa đạt năng lực. |
| `interview_runs.session_id`, `state_version` | Khóa phiên và phiên bản trạng thái được backend commit. |
| `interview_runs.snapshot_json` | Snapshot chi tiết: chuẩn đánh giá, turns, judgments, ledger và tiến trình. Mỗi phiên có một hàng được cập nhật; lịch sử lượt hỏi nằm bên trong snapshot. |
| `interview_runs.public_json` | Bản hiển thị rút gọn, gồm turns và report; không chứa toàn bộ dữ liệu chẩn đoán. |

Quan hệ đọc: `application_profiles.id -> sessions.application_profile_id -> interview_runs.session_id = sessions.id`.

Ví dụ truy vấn đọc nguồn bằng tham số bind của backend (không phải chuỗi SQL để ghép trực tiếp từ input):

```sql
SELECT
    p.id AS application_profile_id,
    p.skill_gap_json,
    p.blueprint_json,
    p.policy_json,
    s.id AS session_id,
    s.attempt_number,
    s.status,
    s.ended_at,
    r.state_version,
    r.snapshot_json,
    r.public_json
FROM application_profiles p
LEFT JOIN sessions s ON s.application_profile_id = p.id
LEFT JOIN interview_runs r ON r.session_id = s.id
WHERE p.id = :application_profile_id
  AND p.user_id = :user_id
ORDER BY s.attempt_number ASC;
```

Các cột hồ sơ lặp lại trên mỗi hàng phiên; nhóm dữ liệu theo `application_profile_id` và `session_id` trước khi xử lý. Hồ sơ chưa bắt đầu có thể chưa có blueprint/snapshot. Truy vấn này chỉ đọc dữ liệu nguồn, không thay thế thuật toán tổng hợp.

## 2. Gap dự đoán trước phỏng vấn

Nguồn: từng phần tử `application_profiles.skill_gap_json[]`. Snapshot cũng giữ đầu vào tại `skills[]`, nhưng contract InterviewSkill không giữ mọi field của kết quả C2; ví dụ `severity` không thuộc contract này.

| Field | Ý nghĩa và cách dùng |
|---|---|
| `jd_skill_id` | ID kỹ năng theo JD. |
| `matched_cv_skill_id` | Kỹ năng trong CV được ghép với kỹ năng JD; có thể null. |
| `semantic_alignment` | MATCH/PARTIAL/MISSING: mức khớp từ tài liệu, không phải kết luận năng lực sau phỏng vấn. |
| `is_substituted` | Có dùng kỹ năng tương đương để ghép hay không. |
| `required_proficiency` | Mức yêu cầu 1–5 ước lượng từ JD. |
| `candidate_proficiency` | Mức năng lực ước lượng từ CV; không cập nhật thành điểm năng lực quan sát sau mỗi lượt. |
| `gap_magnitude` | Độ thiếu hụt dự đoán chuẩn hóa 0–1, không phải xác suất yếu hoặc phần trăm kiến thức thiếu. |
| `importance_weight` | Độ quan trọng của kỹ năng trong JD. |
| `severity`, `priority` | Mức nghiêm trọng/ưu tiên ban đầu, theo trọng số và gap. Không phản ánh tự động tiến bộ qua phỏng vấn. |
| `cv_evidence_spans`, `jd_evidence_spans` | Trích dẫn tài liệu hỗ trợ phân tích. |
| `jd_reasoning`, `context_job` | Giải thích mức yêu cầu và ngữ cảnh kinh nghiệm trong CV. |
| `job_tasks[]` | Các nhiệm vụ cụ thể trong JD. |
| `job_tasks[].task_id`, `description`, `evidence_spans` | ID, nội dung và nguồn trích của nhiệm vụ. |
| `job_tasks[].required_level`, `requirement_kind`, `level_basis` | Mức yêu cầu; REQUIRED/OPTIONAL/UNSPECIFIED; cơ sở EXPLICIT/INFERRED/FALLBACK. |
| `c_evidence` | Tỷ lệ bằng chứng CV giàu ngữ cảnh; không phải confidence năng lực phỏng vấn. |
| `recency_flag` | Cờ recency của kỹ năng theo phân tích CV. |
| `degraded`, `flags` | Cảnh báo fallback/chất lượng/provenance của pipeline. |
| `suggested_strategy` | Gợi ý chiến lược hỏi ban đầu, không phải kế hoạch học. |

Nguồn định nghĩa: `ai-service/skill_gap/domain/models.py` và `ai-service/adaptive_questioning/schemas/skill_gap_input.py`.

## 3. Chuẩn người dùng cần đạt

Nguồn: `application_profiles.blueprint_json.objectives[]`, hoặc `snapshot_json.objectives[objective_id].objective` của phiên tương ứng.

| Field | Ý nghĩa và cách dùng |
|---|---|
| `objective_id`, `requirement_id`, `skill_id` | Định danh mục tiêu, yêu cầu nguồn và kỹ năng. Một kỹ năng có thể có nhiều mục tiêu. |
| `claim` | Nhiệm vụ/năng lực cụ thể cần thể hiện theo JD. |
| `required_proficiency` | Mức yêu cầu C2, thang 1–5. |
| `target_depth` | Độ sâu cần kiểm tra: L1 nền tảng, L2 vận dụng, L3 phân tích/giải quyết vấn đề, L4 thiết kế/đánh đổi. Không quy đổi trực tiếp từ proficiency 1–5. |
| `depth_basis`, `depth_rationale`, `depth_evidence_spans` | Cơ sở, giải thích và trích dẫn khi xác định target depth. |
| `requirement_kind`, `inferred`, `jd_evidence_spans` | Tính bắt buộc, thông tin suy luận và nguồn JD. |
| `rubric_version`, `rubric_fingerprint` | Phiên bản và dấu vân tay chuẩn đánh giá; không ghép kết quả khác chuẩn chỉ vì trùng tên kỹ năng. |
| `criteria[].criterion_id`, `description` | ID và nội dung tiêu chí cụ thể. |
| `criteria[].expected_evidence` | Biểu hiện cần quan sát để đánh giá tiêu chí. |
| `criteria[].below_target`, `at_target`, `above_target` | Mô tả chuẩn dưới/đạt/vượt yêu cầu; là đầu vào để xác định mục tiêu học. |
| `criteria[].essential` | Tiêu chí thiết yếu đối với kết luận mục tiêu. Khác với objective.requirement_kind. |
| `suitable_modes[]` | Dạng hỏi phù hợp, lý do và các chỉ số tiêu chí có thể đo được. |
| `extension_depth`, `extension_criterion_ids` | Chuẩn kiểm tra cao hơn nếu có; không phải yêu cầu bắt buộc để đạt target. |
| `estimated_seconds` | Ước tính phục vụ ngân sách phỏng vấn; không phải thời lượng học đề xuất. |

## 4. Câu hỏi và câu trả lời gốc

Nguồn: `snapshot_json.turns[]`. `pending_turn` là câu đang chờ trả lời, chưa phải bằng chứng đã đánh giá.

| Field | Ý nghĩa và cách dùng |
|---|---|
| `turn_id`, `objective_id`, `skill_id` | Truy vết lượt và mục tiêu. |
| `mode` | CODING/DEBUGGING/DESIGN/TECHNICAL_EXPLANATION/BEHAVIORAL. |
| `action` | INITIAL, CLARIFY, FOLLOW_UP, ASK_EASIER, VERIFY_CONTRADICTION hoặc PROBE_DEEPER. Cho biết mục đích câu hỏi. |
| `question_depth` | Độ sâu thực tế của câu hỏi; có thể khác target_depth. |
| `question.text` | Nội dung câu hỏi gốc. |
| `question.criterion_ids` | Tiêu chí được hỏi. Luồng hiện tại nhắm một tiêu chí mỗi câu. |
| `question.assistance` | NONE/CLARIFICATION/HINT: điều kiện hỗ trợ khi hỏi. |
| `question.evidence_scope` | ID bối cảnh/bài toán dùng để đối chiếu trường hợp đã kiểm tra. Do generator khai báo, không bảo đảm mọi paraphrase được nhận diện. |
| `answer` | Câu trả lời gốc được gửi để chấm. VOICE được chấm trên văn bản phiên âm đã gửi. |
| `judgment.observations[]` | Các quan sát cho câu trả lời; cấu trúc ở mục 5. |
| `judgment.explicit_inability`, `inability_excerpt` | Có lời thừa nhận không làm được nhiệm vụ và trích dẫn tương ứng; không suy ra từ im lặng/lạc đề. |
| `judgment.feedback_contains_hint` | Đánh dấu feedback có lộ gợi ý để theo dõi ảnh hưởng tới bằng chứng về sau. |
| `judgment.feedback`, `introduction` | Nhận xét ngắn và lời chuyển tiếp hội thoại. Không phải bản giải thích bài học đầy đủ. |

`difficulty` là field tương thích cũ; dùng `question_depth` và `target_depth` để diễn giải độ sâu trong V2.

## 5. Bằng chứng và phần còn chưa rõ

Nguồn: `snapshot_json.objectives[objective_id].evidence_history[]`. Ledger được dedup; từng `turn.judgment` vẫn lưu quan sát theo lượt gốc.

| Field | Ý nghĩa và cách dùng |
|---|---|
| `criterion_id`, `turn_id` | Bằng chứng cho tiêu chí nào, từ lượt nào. |
| `response_excerpt` | Trích đoạn nguyên văn trong câu trả lời, đã qua validator. |
| `response_line_range` | Khoảng dòng liên tục 1-based, hai đầu bao gồm, nếu judge dùng cách trích theo dòng. |
| `observation` | SUPPORTS: ủng hộ tiêu chí; CONTRADICTS: thể hiện trái chuẩn; UNCLEAR: chưa rõ; NO_EVIDENCE: chưa có bằng chứng. |
| `performance` | BELOW/AT_TARGET/ABOVE/UNDETERMINED cho câu hỏi đang được đánh giá. Phải đọc cùng question_depth; AT_TARGET ở bài L1 chưa chứng minh đạt target L2. |
| `rationale` | Lý do diễn giải của AI dựa vào câu trả lời. Không mặc định là nguyên nhân gốc đã được xác minh. |
| `unresolved_aspects` | Khía cạnh chưa làm rõ ở thời điểm quan sát; không mặc định là kiến thức người dùng thiếu. |
| `question_depth`, `evidence_scope` | Độ sâu và bối cảnh của bằng chứng. |
| `independent` | Cờ bằng chứng đủ điều kiện độc lập theo việc theo dõi hỗ trợ trong engine; không phải bảo đảm thực nghiệm về tính độc lập. |
| `explicit_inability` | Có thừa nhận không làm được nhiệm vụ. |
| `resolves_contradiction` | Quan sát được gắn để giải quyết mâu thuẫn; engine chỉ xử lý trong lượt xác minh phù hợp. |

Nguồn trạng thái mục tiêu: `snapshot_json.objectives[objective_id]`.

| Field | Ý nghĩa và cách dùng |
|---|---|
| `assessment` | Kết luận mục tiêu trong phiên. Đọc theo trạng thái ở mục 7. |
| `criterion_results[criterion_id]` | Bằng chứng target độc lập đang được giữ cho tiêu chí. Không phải kết luận đầy đủ: vẫn phải xét contradictions, corroboration và assessment. |
| `contradictions` | Các criterion ID có bằng chứng mâu thuẫn chưa giải quyết trong phiên. |
| `assisted_criteria` | Các criterion ID đã bị ảnh hưởng bởi gợi ý theo engine. |
| `criterion_progress[criterion_id].unresolved_aspects` | Phần chưa rõ cập nhật gần nhất trong phiên; đọc cùng lịch sử, không ghép mọi gap cũ thành điểm yếu hiện tại. |
| `criterion_progress[criterion_id].turns_spent` | Số lượt đã đánh giá; không phải điểm năng lực. |
| `criterion_progress[criterion_id].clarification_spent`, `easier_spent`, `deeper_spent` | Đã dùng làm rõ/chẩn đoán dễ hơn/mở rộng cho tiêu chí hay chưa. |
| `criterion_progress[criterion_id].observed_cases`, `stagnant_turns`, `stop_reason` | Các bối cảnh đã quan sát, số lượt không thêm tiến triển theo heuristic và lý do dừng. |
| `lifecycle`, `excluded_reason`, `stop_reason` | Tiến trình, lý do không được chọn hoặc dừng mục tiêu. CLOSED không đồng nghĩa đạt. |

Snapshot cũng có `schema_version`, `engine_version`, `state_version`, `is_finished`, `termination_reason`, `config` và `policy`. Dùng chúng để kiểm tra phiên bản và điều kiện đánh giá. Dữ liệu cũ thiếu depth/provenance không tự được xem là tương đương bằng chứng mới.

## 6. Báo cáo và năng lực hiện tại

### Báo cáo một phiên

Nguồn: `interview_runs.public_json.report`.

| Field | Ý nghĩa và giới hạn |
|---|---|
| `objectives[].criteria[]` | ID, mô tả, assessment, số lượt và lý do dừng theo tiêu chí trong report. |
| `objectives[].strengths`, `weaknesses` | Các diễn giải từ bằng chứng; weaknesses không thay thế kết luận đủ bằng chứng của toàn mục tiêu. |
| `objectives[].covered_criteria`, `missing_criteria` | Phần đã có kết quả target không mâu thuẫn và phần chưa được giải quyết. Covered không có nghĩa mọi phần đều đạt; missing không đồng nghĩa đã xác nhận yếu. |
| `objectives[].evidence`, `evidence_turn_ids` | Bằng chứng đã lọc, chủ yếu độc lập ở target. Không bao gồm đầy đủ mọi chẩn đoán dễ hơn/hỗ trợ. |
| `study_recommendations`, `objectives[].study_recommendations` | Gợi ý ôn dưới dạng chuỗi, được suy ra theo rule. Có thể đề xuất củng cố hoặc ôn khi chưa đủ kết luận; không phải danh sách gap đã được xác nhận hoàn toàn. |
| `progress` | Tỷ lệ mục tiêu được chọn đã đóng. Không phải tiến độ học hoặc tỷ lệ đạt. |
| `evidence_coverage` | Độ bao phủ kết quả tiêu chí không mâu thuẫn trong các mục tiêu được chọn; có thể bao gồm thể hiện dưới chuẩn. Không phải phần trăm năng lực. |
| `target_attainment` | Tỷ lệ AT/ABOVE trong nhóm mục tiêu có assessment AT/ABOVE/BELOW theo implementation hiện tại; null nếu nhóm rỗng. Không dùng để kết luận tất cả yêu cầu JD đã đạt. |

### Năng lực tổng hợp qua các lượt

Chưa có bảng SQL lưu riêng kết quả này. `ApplicationCompetencyService` đọc các snapshot và gọi `CompetencyProjection` khi được yêu cầu. Có thể gọi service trong cùng backend; API có sẵn là `GET /api/v1/application-profiles/{id}/competency`.

| Field của projection | Ý nghĩa |
|---|---|
| `policyVersion` | Phiên bản quy tắc tổng hợp, hiện là competency-1. |
| `completedAttempts`, `incompatibleAssessments` | Số lượt kết thúc có câu trả lời được xét và số đánh giá mục tiêu không tương thích bị bỏ qua. |
| `skills[].skillId`, `baselineAlignment`, `assessment` | Kỹ năng, khớp CV/JD ban đầu và kết luận năng lực hiện tại. |
| `skills[].evidencedCriteria`, `totalCriteria` | Số tiêu chí có bằng chứng và tổng tiêu chí; có bằng chứng không đồng nghĩa đạt. |
| `skills[].objectives[].id`, `claim`, `assessment`, `explanation` | Mục tiêu và kết luận tổng hợp với giải thích. |
| `skills[].objectives[].criteria[].id`, `description`, `essential`, `assessment`, `evidence` | Chi tiết và tín hiệu theo tiêu chí. Không tự thay thế assessment của cả mục tiêu bằng kết quả của một tiêu chí. |
| `lastChecked` | Lượt kiểm tra gần nhất; có thể chưa đủ để đổi kết luận. |
| `lastAssessment` | Nguồn kết luận/tín hiệu đang được giữ theo cấp tương ứng; có thể khác lastChecked. |
| `evidence[].source`, `turnId`, `question`, `responseExcerpt`, `rationale`, `performance`, `context` | Nguồn lượt, câu hỏi, bằng chứng và bối cảnh. source có sessionId, attemptNumber, assessedAt. |

Projection chỉ xét lượt đã kết thúc và có câu trả lời, kiểm tra tương thích rubric và chọn bằng chứng đủ điều kiện. Lượt chưa hỏi lại một mục không tự xóa kết luận cũ. Khi có bằng chứng trái ngược, có thể cần hai lượt xác nhận nhất quán về sau ở các bối cảnh khác nhau để giải quyết.

### CompetencyProjection tổng hợp như thế nào?

Đây là thuật toán tất định chạy trên dữ liệu đã lưu, không gọi AI để chấm lại, không lấy trung bình điểm và không đếm lượt đúng/sai để tính phần trăm năng lực.

1. Duyệt phiên theo `attempt_number` tăng dần. Chỉ xét phiên có snapshot/public state đều `is_finished=true` và có turns; mục tiêu phải thực sự có câu trả lời không trống và không bị EXCLUDED.
2. Kiểm tra cùng objective ID, skill ID, criteria, target depth và rubric fingerprint (hoặc cơ chế tương thích fallback cho dữ liệu cũ). Bỏ qua đánh giá không tương thích.
3. Chọn bằng chứng đúng criterion, có turn gốc và trích dẫn trong answer, độc lập, không phải câu có HINT, ở đúng target depth, với observation/performance hợp lệ.
4. Tạo tín hiệu theo tiêu chí. Ưu tiên bằng chứng đang được giữ trong criterion_results nếu nó nằm trong tập hợp lệ; nếu không, dùng bằng chứng hợp lệ cuối. Contradictions còn tồn tại tạo tín hiệu NEEDS_VERIFICATION. AT_TARGET/ABOVE ở target tạo tín hiệu đạt; BELOW tạo tín hiệu dưới yêu cầu.
5. Chỉ tiếp nhận kết luận đầy đủ của mục tiêu nếu assessment của phiên đủ điều kiện và được bằng chứng tương ứng hỗ trợ. Kết luận đạt cần mọi tiêu chí essential được hỗ trợ trong chính phiên đó. Không tự ghép các tiêu chí đạt rời rạc từ nhiều phiên thành một kết luận toàn mục tiêu. ABOVE cần thêm bằng chứng extension; thiếu thì chỉ giữ AT.
6. Đối chiếu các tín hiệu theo thời gian. Bằng chứng trái chiều tạo yêu cầu xác minh; cần hai phiên nhất quán theo hướng mới với bối cảnh đã biết, không trùng nhau để giải quyết. Bối cảnh được đối chiếu bằng evidence_scope đã chuẩn hóa, chưa phải kiểm tra tương đương ngữ nghĩa đầy đủ.
7. Nếu lượt mới không có tín hiệu quyết định, thường giữ kết luận cũ. Tuy nhiên, nếu tín hiệu tiêu chí mới làm kết luận mục tiêu cũ không còn đáng tin, có thể trả NEEDS_VERIFICATION hoặc INSUFFICIENT_EVIDENCE dù chưa có kết luận đầy đủ mới.
8. Tổng hợp lên skill theo bảng bên dưới.

| Tình trạng các mục tiêu của skill (xét theo thứ tự ưu tiên) | Skill assessment |
|---|---|
| Chưa có mục tiêu hoặc mọi mục tiêu NOT_ASSESSED | NOT_ASSESSED |
| Có mục tiêu NEEDS_VERIFICATION | NEEDS_VERIFICATION |
| Có mục tiêu BELOW hoặc NOT_DEMONSTRATED, không còn mâu thuẫn ở trên | DEMONSTRATED_BELOW_TARGET |
| Mọi mục tiêu đều AT/ABOVE | AT; chỉ ABOVE nếu mọi mục tiêu đều ABOVE |
| Có mục tiêu đạt, phần còn lại chưa đủ kết luận | PARTIALLY_ASSESSED |
| Các trường hợp đã kiểm tra còn lại | INSUFFICIENT_EVIDENCE |

Lưu ý hiện trạng: bước tổng hợp skill xét các mục tiêu thuộc skill, chưa loại riêng objective OPTIONAL. Không tự diễn giải kết quả skill như thể nó chỉ xét các nhiệm vụ bắt buộc.

Ví dụ cùng một mục tiêu, mỗi phiên có kết luận đầy đủ và bằng chứng hợp lệ:

| Phiên | Kết quả phiên | Bối cảnh | Kết luận tổng hợp |
|---|---|---|---|
| 1 | Dưới yêu cầu | A | Dưới yêu cầu |
| 2 | Đạt | B | Cần xác minh vì trái kết quả cũ |
| 3 | Đạt | Vẫn B | Vẫn cần xác minh |
| 4 | Đạt | C khác B | Đạt; phiên 2 và 4 cung cấp hai xác nhận theo hướng mới |

Ví dụ này không có nghĩa luôn phải trải qua bốn phiên. Nếu chưa có kết luận trái chiều, một phiên đáp ứng đầy đủ điều kiện có thể xác nhận đạt ngay. Policy hiện tại là quy tắc vận hành của hệ thống, không phải thang đo đã được hiệu chuẩn trên người dùng.

## 7. Diễn giải trạng thái cho ôn luyện

| Trạng thái | Cách hiểu |
|---|---|
| `NOT_ASSESSED` | Chưa kiểm tra; không gán là yếu. |
| `INSUFFICIENT_EVIDENCE` | Đã kiểm tra nhưng chưa đủ kết luận; cần thêm bằng chứng. |
| `NOT_DEMONSTRATED` | Chưa thể hiện được mục tiêu theo điều kiện đánh giá và bằng chứng chẩn đoán; không khẳng định thiếu toàn bộ kỹ năng. |
| `DEMONSTRATED_BELOW_TARGET` | Kết luận mục tiêu dưới yêu cầu có đủ điều kiện theo engine; phù hợp đề xuất ôn. |
| `DEMONSTRATED_AT_TARGET` | Đáp ứng mục tiêu đã kiểm tra. |
| `DEMONSTRATED_ABOVE_TARGET` | Có thêm bằng chứng đáp ứng chuẩn mở rộng đã định nghĩa. |
| `NEEDS_VERIFICATION` | Trạng thái tổng hợp: có mâu thuẫn cần xác minh. |
| `PARTIALLY_ASSESSED` | Trạng thái tổng hợp kỹ năng: mới có một phần mục tiêu đạt, chưa đủ phủ toàn bộ. |

Không suy ra kết luận mục tiêu dưới yêu cầu chỉ từ một evidence.performance=BELOW hoặc một criterion_results. Assessment theo tiêu chí trong projection phản ánh tín hiệu riêng; phải đọc cùng assessment mục tiêu và giải thích.

## 8. Có cần thêm dữ liệu không?

### Cần thống nhất trước khi tích hợp

1. Dùng khóa liên kết gồm `application_profile_id`, `objective_id`, `criterion_id`, `rubric_fingerprint` cho đầu việc ôn; lưu nguồn `session_id`/`turn_id` nếu đầu việc sinh từ bằng chứng. Các ID nguồn đã có; liên kết trong bảng đầu việc do module ôn luyện bổ sung.
2. Dùng `CompetencyProjection` cho năng lực hiện tại, lấy snapshot để bổ sung chi tiết chẩn đoán. Không chỉ đọc phiên mới nhất, không tự lấy trung bình điểm, không sửa baseline CV/JD.
3. Thống nhất cấu trúc JSON và cách đọc qua backend dùng chung. Không bắt buộc API mới hoặc migration mới chỉ để lấy các field hiện có.
4. Đối chiếu năng lực mới khi hiển thị/cập nhật kế hoạch. Đạt qua phỏng vấn cập nhật mức cần ưu tiên, không tự đánh dấu hoàn thành đầu việc hoặc checklist. Cơ chế đọc/cập nhật này thuộc tích hợp ôn luyện, hiện chưa có module thực thi.

### Cập nhật giao diện ôn luyện sau phỏng vấn mới

Ba trạng thái có nguồn độc lập: năng lực lấy từ phỏng vấn; trạng thái đầu việc lấy từ thao tác người dùng; tiến độ checklist lấy từ các mục được người dùng đánh dấu.

| Thay đổi từ phỏng vấn | Hành vi đề xuất của module ôn luyện |
|---|---|
| Mục tiêu từ dưới yêu cầu sang đạt sau khi tổng hợp/xác minh đủ | Cập nhật nhãn năng lực, giảm ưu tiên hoặc cho lưu trữ đầu việc liên quan. Giữ ghi chú, checklist và trạng thái học. |
| Người dùng không học/không đánh dấu nhưng đã được xác nhận đạt | Vẫn cập nhật năng lực. Không tự coi đầu việc đã được thực hiện. |
| Chỉ một tiêu chí đạt, mục tiêu còn chưa đủ bằng chứng | Chỉ ghi nhận đúng phần đã đạt; không đóng toàn bộ gap của skill. |
| Lượt mới không hỏi nội dung cũ | Không xóa kết luận đã có hoặc tạo lại đầu việc chỉ vì phiên mới thiếu mục đó. |
| Có bằng chứng trái chiều | Hiển thị cần xác minh; không tự gọi là đã khắc phục hoặc chắc chắn yếu. |
| Người dùng tự đánh dấu hoàn thành bài học | Cập nhật tiến độ học; năng lực kiểm chứng chưa tự chuyển sang đạt. |

Module ôn luyện cần thực hiện đối chiếu khi đọc lại kế hoạch hoặc sau khi phiên mới kết thúc. Hiện chưa có event, job đồng bộ hoặc API tạo kế hoạch ôn được triển khai để tự thực hiện các hành vi trên.

### Nên bổ sung một cấu trúc bàn giao suy ra từ dữ liệu hiện có

Không bắt buộc lưu bảng mới. Có thể tạo read model/DTO dùng chung với các field đề xuất sau (chưa tồn tại dưới dạng contract này):

| Field đề xuất | Mục đích |
|---|---|
| `application_profile_id`, `skill_id`, `objective_id`, `criterion_id`, `rubric_fingerprint` | Liên kết chính xác nội dung học với chuẩn đánh giá. |
| `current_assessment`, `assessment_scope`, `assessment_source` | Kết luận hiện tại, cấp kết luận objective/criterion và nguồn; tránh trộn tín hiệu riêng với kết luận toàn mục tiêu. |
| `target_description`, `target_depth`, `expected_evidence` | Đích cần đạt; lấy từ blueprint. |
| `recommendation_type` | Phân biệt REMEDIATE/REINFORCE/ASSESS_MORE/VERIFY_CONFLICT; cần định nghĩa rule rõ ràng. |
| `reason`, `unresolved_aspects`, `source_evidence` | Lý do đề xuất, phần chưa rõ và trích dẫn nguồn. |
| `source_state_version`, `competency_policy_version` | Truy vết snapshot và rule khi sinh đề xuất; không đại diện riêng lẻ cho toàn bộ lịch sử hồ sơ. |

`study_recommendations` hiện là chuỗi; không nên parse câu tiếng Việt để đoán lại criterion ID hoặc loại đề xuất. Có thể giữ chuỗi cho UI và bổ sung cấu trúc trên cho tích hợp.

### Chỉ cần bổ sung nếu muốn ôn tự động sâu hơn

- Taxonomy chủ đề/concept và quan hệ kiến thức tiên quyết: chưa có cấu trúc chuẩn hóa trong dữ liệu phỏng vấn hiện tại.
- Phân loại lỗi/nhầm lẫn kiến thức: chưa có error_type/misconception chuẩn hóa; rationale của AI chỉ là một nguồn gợi ý, cần ghi rõ mức suy luận.
- Bằng chứng chạy code nếu muốn khẳng định code thực thi đúng: hiện chưa có kết quả thực thi/test case làm căn cứ đánh giá.

Không cần thêm trường phần trăm confidence hoặc root_cause như thể đã đo chính xác nếu chưa có phương pháp hiệu chuẩn/xác minh.

## 9. Kiểm tra khi tích hợp

Danh sách dưới đây là các tình huống cần xác minh khi xây module ôn luyện, không phải tuyên bố module đó đã có test:

- Hồ sơ mới chỉ có CV/JD: hiển thị gap dự đoán, không gán là điểm yếu đã kiểm chứng; blueprint có thể chưa có.
- Phiên đang chạy hoặc dừng trước câu trả lời đầu: không tự cập nhật năng lực tổng hợp.
- Phiên hết thời gian/chưa đủ bằng chứng: không tự tạo kết luận yếu từ missing criteria.
- Có gap được xác nhận: đầu việc gắn đúng profile/objective/criterion/rubric và có nguồn bằng chứng.
- Người dùng không đánh dấu học nhưng đạt sau phỏng vấn: năng lực đổi, checklist và tiến độ học giữ nguyên.
- Hoàn thành checklist nhưng chưa có bằng chứng đạt: tiến độ học đổi, năng lực giữ theo kết luận phỏng vấn.
- Chỉ kiểm tra một phần skill: không coi toàn skill đã đạt.
- Lượt mới không hỏi nội dung cũ: không làm mất kết luận cũ hoặc tạo trùng đầu việc.
- Kết quả trái chiều: phản ánh NEEDS_VERIFICATION và quy tắc xác nhận; lặp cùng bối cảnh không đủ.
- Sai hồ sơ/người dùng hoặc rubric không tương thích: không ghép dữ liệu vào kế hoạch hiện tại.
- Reload/restart backend: dữ liệu gốc vẫn đọc được từ DB; projection được tính lại từ nguồn đó.

## 10. Nguồn code

- `ai-service/skill_gap/domain/models.py`: kết quả CV/JD và JobTask.
- `ai-service/adaptive_questioning/evidence/models.py`: snapshot, blueprint, turns, observations, ledger và report.
- `ai-service/adaptive_questioning/evidence/assessment.py`: validation, ghi bằng chứng và kết luận.
- `ai-service/adaptive_questioning/evidence/criterion_progress.py`: tiến trình theo tiêu chí.
- `ai-service/adaptive_questioning/evidence/reporting.py`: báo cáo rút gọn và gợi ý ôn.
- `backend/src/main/java/fit/iuh/modules/evidence/EvidenceStore.java`: commit snapshot/public state.
- `backend/src/main/java/fit/iuh/modules/application/CompetencyProjection.java`: tổng hợp nhiều lượt.
- `backend/src/main/java/fit/iuh/modules/application/ApplicationCompetencyService.java`: đọc theo quyền chủ hồ sơ.
- `backend/src/main/resources/db/migration/V2__evidence_interviews.sql`, `V3__application_profiles.sql`: lưu trữ và liên kết SQL.
