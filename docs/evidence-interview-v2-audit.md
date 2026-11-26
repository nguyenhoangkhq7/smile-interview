# Audit và hoàn thiện Evidence-driven Interview V2

Ngày kiểm chứng: 07/11/2026. Phạm vi: tổ chức phỏng vấn và đánh giá bằng chứng trong V2. Giữ nguyên contract Module 1 `w_j`/`soft_match` và công thức nghiên cứu C2.

Lưu ý lịch sử: ngày 09/11/2026 đã gỡ belief/raw_belief/tag và engine C3 cũ. Những mô tả belief trong audit này ghi nhận phiên bản trước; xem [contract hiện tại](evidence-interview-v2.md).

## 1. Kết quả audit trước khi sửa

Các số dòng **trước sửa** dưới đây ghi nhận từ source lúc bắt đầu audit; phần 3 dẫn đến vị trí implementation hiện tại. Không coi tất cả yêu cầu trong đề bài là tính năng chưa có.

| Vấn đề | Trạng thái trước sửa | Bằng chứng thực tế trước sửa |
|---|---|---|
| Thang question depth độc lập | MISSING | `ai-service/adaptive_questioning/evidence/planning.py:79` gán difficulty = required_proficiency; `workflow.py:91` chỉ trừ 1 khi EASIER, DEEPER vẫn giữ nguyên proficiency |
| Blueprint/rubric theo task, nhiều suitable modes | ALREADY_IMPLEMENTED | `planning.py:10` tạo requirement theo task; `provider.py:18` yêu cầu rubric và mode theo nhiệm vụ; `models.py:80` có objective/criteria/suitable_modes |
| Chọn mode khi chạy MIXED | PARTIAL | `planning.py:78` dùng `modes[0]`; chưa xét criterion coverage hoặc cân bằng dạng. FOCUSED đã có lọc và báo lỗi |
| Adaptive action và giới hạn ngân sách | PARTIAL | `assessment.py:75` đã có clarify/follow-up/easier/verify; `workflow.py:65` đã chặn global/time. Local budget ở dòng 78 được tính sau next_action; DEEPER chưa tăng độ sâu thật |
| Grounding judgment và CV prior | ALREADY_IMPLEMENTED | `assessment.py:10` kiểm tra exact excerpt/criterion IDs/belief; `workflow.py:36` không đưa CV score cho Judge. Belief không quyết định sufficiency |
| Evidence validity và sufficiency | PARTIAL | `assessment.py:50` đã loại HINT/easier khỏi target, nhưng dòng 59 ghi đè evidence cũ. Dòng 68 dùng hai lần thừa nhận không biết; dòng 74 có thể ABOVE ngay tại target. BELOW có thể kết luận sau một lượt |
| Importance và fairness giữa skill | ALREADY_IMPLEMENTED | `planning.py:61` xếp importance/priority và một lượt mỗi skill; MATCH vẫn được chọn |
| Follow-up reserve và phân bổ lại | PARTIAL | `planning.py:73` có thể dùng toàn bộ câu cho initial objectives; `workflow.py:72` dành lượt cho queue còn lại nhưng chưa tái kích hoạt objective ngoài ngân sách khi kết thúc sớm |
| Seniority, task target và tính nhất quán | PARTIAL | `planning.py:49` đã khóa task.required_level đúng C2; thiếu depth provenance riêng. Rubric được giữ trong snapshot, chưa có cách nhận diện rubric khác nhau giữa các phiên |
| Retry, persistence, concurrent writes | ALREADY_IMPLEMENTED | `backend/src/main/java/fit/iuh/modules/evidence/EvidenceService.java:46` replay trước model call; `EvidenceStore.java:36` khóa session và kiểm tra version. Giữ nguyên implementation |

## 2. Phần giữ nguyên

- Các lớp provider/blueprint/workflow/reporting hiện có, không xây V3 hoặc engine song song.
- C2 task/proficiency, các công thức gap, matcher mock và điểm tích hợp SBERT/GNN.
- Backend ownership, transaction, receipt, optimistic version và khóa commit.
- Endpoint, request/response bắt buộc, database schema và frontend. Public evidence giữ cấu trúc cũ; metadata depth/scope/independence chỉ lưu nội bộ. Public report lấy target evidence độc lập, gồm cả thuận và nghịch; diagnostic/hint/extension nằm trong ledger và transcript.
- Không bổ sung học tập, ghi chú, sandbox chạy code hoặc gọi LLM thật để tự chấm implementation.

## 3. Files, classes và functions đã sửa

Tất cả đường dẫn Python sau tính từ `ai-service/adaptive_questioning/evidence/`.

| File/vị trí | Thay đổi |
|---|---|
| `models.py`, `Objective`, `ObjectiveState`, `Turn`, `Snapshot` | Thêm target/current depth, provenance, extension standard, mode coverage, ledger, hint tracking, policy snapshot và rubric fingerprint. Giữ các field cũ để đọc snapshot cũ |
| `policy_config.py:7`, `InterviewPolicy`; `configured_policy()` | Heuristic có cấu hình, validation và version; snapshot khóa policy trong phiên |
| `depth.py:15`, `ground_depth()`; `question_depth()` | Định nghĩa L1–L4 dùng chung; lựa chọn và điều chỉnh độ sâu |
| `planning.py:47`, `BlueprintBuilder.build()` | Giữ coverage và stable IDs; kiểm tra task mode, depth provenance, criterion coverage và extension anchors |
| `planning.py`, `_allocate()`, `select_mode()`, `_rank()` | Ưu tiên core/gap, mode theo task/criteria, reserve follow-up và lý do chọn mode |
| `assessment.py:13`, `validate_judgment()` | Giữ grounding, thêm consistency của observation/performance |
| `assessment.py`, `_record_observation()`, `_update_target_result()` | Ledger giữ hai chiều, dedup, đánh dấu assistance; target results không bị diagnostic/extension ghi đè |
| `assessment.py`, `assess()`, `next_action()` | Sufficiency theo essential criteria, target depth và diagnostic corroboration; chỉ probe higher standard khi có cấu hình và anchor |
| `workflow.py:33`, `respond()`; `_advance()`, `_ask()` | Truyền action/depth xuyên suốt; budget trước routing/generation; validation mode/depth/scope; retry có giới hạn; reallocation |
| `workflow.py`, `_retain_legacy_evidence()` | Đọc snapshot cũ không giả định difficulty 1–5 chính là depth L1–L4 |
| `reporting.py:5`, `objective_report()` | Public projection giữ cả thuận/nghịch phù hợp target; strengths/weaknesses dựa trên target result không mâu thuẫn |
| `provider.py:18`, `BlueprintSignature`, `QuestionSignature`, `JudgeSignature` | Đặc tả mode/depth, context độc lập, higher anchor, short/off-topic answers và hint trong feedback |
| `routes.py:12`, `workflow()` | Nạp cấu hình policy phía server, không cho ứng viên sửa policy |
| `tests_adaptive_questioning/test_evidence_workflow.py` | Cập nhật fake provider theo contract nội bộ mới, sửa assertion của quy tắc BELOW/diagnostic |
| `tests_adaptive_questioning/test_evidence_depth_policy.py` | 41 trường hợp chạy sau parametrization, bao gồm API integration và recovery |
| `docs/evidence-interview-v2.md` | Cập nhật tài liệu vận hành tránh mô tả thuật toán cũ |

## 4. Thuật toán chọn câu hỏi và độ sâu

### Blueprint và target

1. Mỗi task trong C2 có một requirement/objective riêng. Thiếu task thì ghi inferred; không bịa task từ tên công nghệ.
2. Proficiency C2 1–5 được bảo toàn. Blueprint diễn giải task để đề xuất depth L1–L4, kèm lý do và trích dẫn từ requirement. Không ánh xạ số proficiency sang depth.
3. Khi không có diễn giải depth kèm provenance, dùng task-verb heuristic có cấu hình: foundation 1, application 2, analysis 3, design/trade-offs 4. Nếu nhiều cue cùng tồn tại thì chọn mức cao nhất; đây là fallback có giới hạn, không phải thang đo đã hiệu chuẩn.
4. Nếu không xác định được depth từ task, dùng `fallback_depth` (mặc định 2, chủ động ghi CONFIGURED_FALLBACK). Seniority chỉ được dùng khi operator cấu hình mapping và có tên cấp độ trong JD evidence nhận được. Mapping mặc định rỗng, không có Intern=L2 hay Junior=L3. Task cụ thể luôn có ưu tiên.
5. Target, proficiency, criteria, anchors và rubric fingerprint được khóa trước câu đầu. Candidate answer không được sửa chúng. Fingerprint thay đổi nếu tiêu chuẩn thay đổi; cùng objective ID chưa đủ để chứng minh hai rubric tương đương.

### Planner và mode

- Nhóm core có importance ≥ 0.7 đứng trước. Trong nhóm core, gap priority trước importance; nhờ vậy Java/SQL thiếu hụt có thể đứng trước Spring MATCH, còn MATCH core vẫn có cơ hội xác minh. Trong nhóm không core, importance trước gap. Optional được xếp sau yêu cầu không optional trong cùng nhóm.
- Một lượt qua các skill trước additional objectives cùng skill. Điều này bảo đảm cơ hội coverage theo skill khi ngân sách cho phép; không bảo đảm phủ mọi competency nếu cấu hình phiên quá nhỏ.
- Mặc định giữ 30% số câu cho follow-up. Số initial slots = min(global budget, max(1, số core skills, budget − ceil(budget × reserve fraction))). Core coverage có thể dùng phần reserve nếu ngân sách quá nhỏ.
- Trừ thời lượng ước tính của initial objectives; objective không vừa được đánh PLAN_BUDGET và NOT_ASSESSED.
- MIXED: task intent phù hợp → nhiều essential criteria đo được hơn → mode ít dùng hơn → thứ tự blueprint khi hòa. Các rule nhận diện task/mode có cấu hình, không dựa vào tên skill. Blueprint hoàn toàn bỏ qua mode task rõ ràng sẽ bị từ chối.
- FOCUSED: chỉ mode người dùng chọn nếu blueprint hỗ trợ. Mode của một objective đã hỏi không thay đổi giữa các lượt.
- Khi queue kết thúc sớm, đưa từng objective PLAN_BUDGET trở lại nếu còn số câu và đủ thời gian ước tính. MODE_FILTER không được tự động bỏ lọc.

### Câu tiếp theo

- INITIAL bắt đầu trực tiếp tại target depth.
- Mâu thuẫn tại target → VERIFY ở target, nếu còn ngân sách và có thể thu bằng chứng độc lập.
- Sai có căn cứ hoặc thừa nhận không giải được → có thể ASK_EASIER thấp hơn một mức, một lần để chẩn đoán. Không tự hạ target.
- Mơ hồ/không liên quan → CLARIFY cùng depth, giữ cùng evidence scope, tối đa một lần; không kết luận yếu vì off-topic.
- Còn essential criteria chưa quan sát → FOLLOW_UP ở target, ưu tiên criterion còn thiếu. Không lặp criterion đã đạt để tăng số lượt.
- Đạt target → dừng objective. Chỉ PROBE_DEEPER khi `allow_extension_probes=true`, đã có extension depth/anchor cao hơn, chưa probe và còn ngân sách. Mặc định tắt.
- NEXT_OBJECTIVE là thao tác đóng objective và lấy objective tiếp theo từ queue; câu đầu của objective tiếp theo vẫn mang action INITIAL.

Generator phải trả đúng mode/depth đã được Router quyết định, criterion IDs hợp lệ, evidence scope không rỗng và câu hỏi không trùng nguyên văn sau chuẩn hóa. Sai contract được retry tối đa 2 lần theo policy. Hết deadline giữa các lần thử thì không gọi tiếp; câu sinh xong sau deadline không được công bố làm pending turn.

## 5. Thuật toán đánh giá và quyết định dừng

**Validity:** substantive observations phải có trích dẫn nguyên văn trong câu trả lời, đủ đúng tập criterion được hỏi; UNCLEAR/NO_EVIDENCE không được gán performance. Inability cần một trích dẫn thừa nhận rõ ràng. Raw belief hợp lệ về số học nhưng không quyết định assessment.

**Independence:** ledger chứa turn ID, depth, concrete case scope và assistance. Evidence trùng criterion/depth/scope/excerpt/performance không được nhân bản. Thay cách diễn đạt không tạo context mới. Câu có HINT hoặc criterion đã lộ lời giải qua feedback không được dùng như bằng chứng độc lập cho phần sau trong objective. Nếu không còn criterion độc lập đo được bằng mode đã chọn, đóng với NO_INDEPENDENT_CRITERIA_IN_MODE và giữ INSUFFICIENT.

**Coverage:** target attainment cần mọi essential criterion có evidence độc lập ở đúng target và không còn contradiction. Một câu trả lời có thể đủ nếu đo đủ criteria; nhiều câu lặp kiến thức không làm tăng coverage. Evidence L1 không tự chứng minh L2.

**Negative evidence:** một câu sai đơn lẻ vẫn INSUFFICIENT. Để kết luận failure ở một essential criterion, cần failure tại target và evidence đối chiếu ở depth chẩn đoán thấp hơn, trên ít nhất `min_failure_contexts` concrete cases khác nhau (mặc định 2). Với target L1, dùng nhiều case foundation khác nhau thay bước hạ depth. Các case phải có substantive evidence hoặc admission rõ ràng; off-topic không tính.

- Nếu mọi essential đã được quan sát/đối chiếu và còn failure hợp lệ → BELOW.
- Nếu mọi essential đều có failure đã đối chiếu, và chưa có thể hiện thành công độc lập tại target hoặc thấp hơn → NOT_DEMONSTRATED cho **objective này**. Không cần người dùng nói “không biết”, không suy ra họ thiếu toàn bộ skill.
- Nếu đủ essential đạt target → AT. Muốn ABOVE phải đồng thời đáp ứng anchors cao hơn đã khai báo ở extension depth trên các essential criteria. Trả lời dài, nhiều thuật ngữ hoặc được Judge gắn ABOVE ngay ở target vẫn chỉ hỗ trợ AT.
- Mâu thuẫn ở target giữ INSUFFICIENT đến lượt VERIFY có evidence giải quyết. Giữ cả observations thuận/nghịch trong ledger, không xóa lịch sử khi resolve.
- Failure ở extension chỉ là kết quả thử sức; không ghi đè target result và không làm trượt target đã đủ evidence.

**Dừng:** global question/time budget được kiểm tra trước routing, local/reservation budget trước hành động sinh tiếp, và kiểm tra lại trước/sau generator. Dừng đủ evidence, không còn criterion độc lập, hết local budget, hết queue, user stop hoặc hết global/time đều có reason. Objective chưa có câu trả lời được đánh giá vẫn NOT_ASSESSED. Budget exhaustion không biến thành kết luận yếu.

## 6. Cấu hình và tương thích

Operator có thể đặt JSON trong biến môi trường `EVIDENCE_POLICY_JSON`, ví dụ:

```json
{"fallback_depth":2,"core_importance":0.7,"reserve_followup_fraction":0.3,"min_failure_contexts":2,"allow_extension_probes":false,"generation_attempts":2}
```

Có thể cấu hình `depth_patterns`, `mode_patterns`, `seniority_fallback_depths`. Đây là cấu hình server; không thêm vào form/API public. Policy được validate và copy sâu vào snapshot khi start; thay biến môi trường hoặc cấu hình workflow không thay chính sách của phiên đang chạy. Nếu cung cấp rule dictionary thì nó thay toàn bộ dictionary mặc định tương ứng.

Snapshot cũ thiếu các field mới vẫn đọc được. Không chuyển số difficulty cũ thành question depth. Evidence chưa biết depth được giữ để audit nhưng khi objective đang hoạt động chuyển tiếp, không dùng nó làm evidence L1–L4 đã xác nhận; câu hỏi mới ở fallback/target đã ghi provenance. Public state đã lưu của phiên hoàn tất không bị chấm lại tự động. Backward compatibility này chủ động không khẳng định evidence cũ tương đương chuẩn mới.

## 7. Kiểm thử và kết quả thực tế

Chạy regression Python sau thay đổi:

```powershell
# cwd: ai-service
python -B -m pytest tests_skill_gap tests_adaptive_questioning -q
```

Kết quả: **200 passed**, bao gồm 41 trường hợp mới qua parametrization và các tests V2 hiện có. Fake provider deterministic kiểm tra policy/state, không mô phỏng bằng chứng chất lượng LLM thật.

Backend trên PostgreSQL 17 tạm:

```powershell
.\scripts\verify-evidence-backend.ps1 -JavaHome 'C:\Program Files\JetBrains\IntelliJ IDEA 2026.2.4\jbr'
```

Kết quả: **18 tests**, 0 failures/errors/skipped. Gồm schema/JPA, replay receipt, stale version, concurrent answers chỉ một commit, transaction rollback, ownership và HTTP serialization. Không thay code backend trong đợt audit này.

`git -c core.safecrlf=false diff --check`: đạt. Frontend/build/migration standalone không chạy lại vì đợt này không sửa frontend/schema; migrations được áp dụng trong backend integration tests. Không gọi LLM thật hoặc tạo chi phí API.

Các kịch bản bắt buộc được đối chiếu với automated tests:

| # | Test / nhóm test |
|---|---|
| 1 | `test_l2_starts_directly_without_proficiency_conversion` |
| 2–3 | `test_wrong_l2_diagnoses_l1_and_l1_success_does_not_pass_target` |
| 4 | `test_ambiguous_l2_clarifies_same_depth_and_case` |
| 5 | `test_target_success_stops_without_mandatory_extension` |
| 6 | `test_failed_l3_preserves_established_l2` |
| 7 | `test_hint_taints_same_criterion_even_on_later_unhinted_question`, feedback hint test |
| 8 | `test_negative_and_positive_evidence_survive_contradiction`, test resolve có sẵn |
| 9 | global budget test, `test_local_cap_prevents_contradiction_probe_generation`, timeout tests |
| 10–11 | `test_core_gaps_precede_core_match_and_optional_missing` |
| 12 | `test_multiple_objectives_same_skill_keep_independent_evidence_ledgers` |
| 13 | `test_same_skill_selects_mode_from_jd_task`, `test_debugging_mode_can_be_l2_without_becoming_coding` |
| 14 | `test_ambiguous_jd_is_inferred_with_configurable_fallback_and_no_title_mapping` |
| 15 | `test_matching_zero_gap_skill_is_verified_with_evidence` với câu trả lời ngắn `ok` |
| 16 | `test_turn_cap_is_not_verification` với NO_EVIDENCE/off-topic |
| 17 | test timeout unasked, budget exclusion và AWS NOT_ASSESSED |
| 18 | `test_above_target_requires_predeclared_extension_and_its_evidence` |
| 19 | invalid question mode/depth/scope tests với retry thành công và retry hết giới hạn |
| 20 | backend `repeatedAnswerReturnsReceiptWithoutCallingAi`, persistence replay/concurrency tests |

API integration `test_api_carries_action_depth_evidence_and_recovery_through_response` đi qua start → respond → JSON snapshot recovery → stop. Kiểm tra ASK_EASIER L1, target vẫn L2, metadata và exact evidence được lưu. Một test workflow khác chạy toàn phiên Java/SQL, và các tests kiểm tra fingerprint/policy/recovery.

## 8. Ví dụ phiên Java Backend Intern

Ví dụ sau minh họa nội dung nghiệp vụ. Test deterministic xác nhận chuỗi state/action/depth tương ứng; đây không phải transcript đã chạy qua LLM thật.

JD yêu cầu: “Implement duplicate ID removal using Java Collections; write SQL queries for filtered records”. C2 giả định proficiency yêu cầu 2 cho hai task; depth L2 được xác định riêng từ nhiệm vụ Application. Java importance 0.95, SQL 0.80. MIXED, tối đa 6 câu, 15 phút, 3 câu/objective.

Blueprint Java: criterion J1 chọn collection và loại trùng đúng; J2 giải thích vì sao phù hợp và chi phí tra cứu trung bình. Target L2, CODING. Không khai báo extension. SQL: S1 SELECT/filter đúng, S2 biểu thức WHERE và projection đúng; L2, CODING.

| Lượt | Câu hỏi / câu trả lời | Judge | Router và câu tiếp theo |
|---|---|---|---|
| 1, Java INITIAL L2 | Hỏi: “Với `[7,7,9]`, viết Java trả về các ID không trùng, không yêu cầu thứ tự.” Đáp: `new HashSet<>(List.of(7, 7, 9))` | J1 có evidence độc lập tại L2; J2 chưa được hỏi. INSUFFICIENT, không hạ điểm vì câu ngắn | FOLLOW_UP tại L2: “Vì sao collection này phù hợp? Chi phí kiểm tra một ID trung bình?” |
| 2, Java FOLLOW_UP L2 | Đáp: “Set không chứa phần tử trùng; HashSet kiểm tra membership trung bình O(1), không cần giữ thứ tự.” | J2 đạt anchor; đủ J1 và J2 → AT | Đóng Java SUFFICIENT_EVIDENCE; NEXT_OBJECTIVE. SQL INITIAL L2: “Bảng events(id,status), viết query lấy id của các dòng status='active'.” |
| 3, SQL INITIAL L2 | Đáp: `SELECT id FROM events WHERE status = 'active';` | Đủ S1/S2 tại L2 → AT | Đóng SQL, queue hết → PLAN_COMPLETE; không bắt buộc hỏi L3 |

Báo cáo: Java và SQL đạt target với turn IDs/trích dẫn tương ứng; không có ABOVE vì chưa đo higher standard. Nếu lượt 1 sai, router có thể hỏi L1 để chẩn đoán. Đúng L1 chưa đủ đạt L2. Nếu câu trả lời mơ hồ thì CLARIFY L2; nếu hết ngân sách khi còn thiếu J2 thì INSUFFICIENT và lý do dừng được lưu.

## 9. Giới hạn còn lại

- Pattern verbs là heuristic có cấu hình. Chúng có thể hiểu sai câu nhiều mệnh đề, phủ định hoặc ngôn ngữ ngoài tập hiện có. Task interpretation có provenance được ưu tiên, nhưng provenance đúng chỉ chứng minh nguồn trích dẫn, không chứng minh diễn giải của LLM đúng.
- Validation mode/depth kiểm tra contract mà generator khai báo. Chưa có đánh giá độc lập về việc nội dung thật có đúng mode/depth đó hay không. Không dùng LLM tự xác nhận kết quả của nó để tuyên bố chính xác.
- `evidence_scope` do generator khai báo; hệ thống dedup được scope/excerpt/câu hỏi đã biết, chưa bảo đảm nhận diện mọi câu paraphrase hoặc bài toán tương đương về mặt ngữ nghĩa. Không cộng turn count thành evidence sufficiency.
- min_failure_contexts, core threshold, time estimates và reserve fraction chưa được hiệu chuẩn trên người dùng thật. NOT_DEMONSTRATED chỉ nói chưa thể hiện được objective trong điều kiện đã hỏi.
- Rubric cố định trong phiên; fingerprint phát hiện khác biệt tiêu chuẩn giữa các phiên. Chưa có shared rubric registry hoặc hiệu chuẩn equivalence giữa hai blueprint do LLM sinh độc lập. Không được so sánh trực tiếp kết quả khác fingerprint như thể cùng chuẩn.
- C3 chỉ nhận JD evidence do C2 cung cấp, chưa nhận toàn bộ JD/title dưới một field seniority riêng. Vì vậy seniority fallback chỉ áp dụng khi thông tin đó hiện diện trong evidence; nếu không, dùng CONFIGURED_FALLBACK và ghi rõ, không tự đoán title.
- Không chạy LLM thật, không benchmark chuyên gia/psychometrics, không chứng minh độ chính xác đánh giá năng lực qua tests. Module 1 vẫn mock có gắn provenance; coding chưa được thực thi.
