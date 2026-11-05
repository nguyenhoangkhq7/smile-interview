package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.modules.assessment.entity.JobCategory;
import fit.iuh.modules.assessment.entity.ResumeAssessment;
import fit.iuh.modules.assessment.entity.SeniorityLevel;
import fit.iuh.modules.assessment.repository.ResumeAssessmentRepository;
import fit.iuh.modules.chunking.repository.DocumentChunkRepository;
import fit.iuh.modules.session.repository.SessionRepository;
import fit.iuh.exception.QuestionBankException;
import fit.iuh.modules.questionbank.dto.*;
import fit.iuh.modules.questionbank.entity.Question;
import fit.iuh.modules.questionbank.entity.QuestionBank;
import fit.iuh.modules.questionbank.repository.QuestionBankRepository;
import fit.iuh.modules.questionbank.service.DifficultyDistributor;
import fit.iuh.modules.questionbank.service.QuestionGenerationService;
import fit.iuh.modules.questionbank.service.SemanticCacheKeyGenerator;
import fit.iuh.modules.questionbank.service.SemanticCacheService;
import fit.iuh.modules.questionbank.service.impl.QuestionBankServiceImpl;
import fit.iuh.modules.rulengine.repository.EvaluationCriteriaRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Duration;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class QuestionBankServiceTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Mock
    private QuestionGenerationService questionGenerationService;
    @Mock
    private DifficultyDistributor difficultyDistributor;
    @Mock
    private ResumeAssessmentRepository assessmentRepo;
    @Mock
    private SessionRepository sessionRepository;
    @Mock
    private DocumentChunkRepository documentChunkRepository;
    @Mock
    private QuestionBankRepository questionBankRepo;
    @Mock
    private SemanticCacheKeyGenerator cacheKeyGenerator;
    @Mock
    private SemanticCacheService cacheService;
    @Mock
    private EvaluationCriteriaRepository evaluationCriteriaRepository;

    private AppProperties appProperties;
    private QuestionBankServiceImpl service;

    @BeforeEach
    void setUp() {
        appProperties = new AppProperties();
        service = new QuestionBankServiceImpl(
                questionGenerationService,
                difficultyDistributor,
                assessmentRepo,
                sessionRepository,
                documentChunkRepository,
                questionBankRepo,
                objectMapper,
                cacheKeyGenerator,
                cacheService,
                evaluationCriteriaRepository,
                appProperties
        );
    }

    @Test
    @DisplayName("QuestionDto correctly deserializes aliases for follow_ups, good_answer_signals, star_format_prompt")
    void testQuestionDtoDeserializationWithAliases() throws Exception {
        String json = """
                {
                  "id": "item_0",
                  "difficulty": "medium",
                  "topic": "Spring Boot Caching",
                  "question": "Làm thế nào để cấu hình Redis Cache trong Spring Boot?",
                  "follow_ups": ["Cache eviction xử lý ra sao?", "TTL cấu hình ở đâu?"],
                  "good_answer_signals": [
                    "Nêu rõ CacheManager",
                    "Hiểu @Cacheable và @CacheEvict"
                  ],
                  "star_format_prompt": "Khuyến khích trả lời theo STAR",
                  "hints": ["Chú ý RedisTemplate", "Serialization"],
                  "components_to_cover": ["RedisCacheConfiguration", "Jedis/Lettuce"]
                }
                """;

        QuestionDto dto = objectMapper.readValue(json, QuestionDto.class);

        assertEquals("item_0", dto.getId());
        assertEquals("medium", dto.getDifficulty());
        assertEquals("Spring Boot Caching", dto.getTopic());
        assertEquals("Làm thế nào để cấu hình Redis Cache trong Spring Boot?", dto.getQuestion());

        assertNotNull(dto.getFollowUpQuestions());
        assertEquals(2, dto.getFollowUpQuestions().size());
        assertEquals("Cache eviction xử lý ra sao?", dto.getFollowUpQuestions().get(0));

        assertNotNull(dto.getEvaluationCriteria());
        assertTrue(dto.getEvaluationCriteria().contains("Nêu rõ CacheManager"));

        assertEquals("Khuyến khích trả lời theo STAR", dto.getStarPrompt());
        assertEquals(2, dto.getHints().size());
        assertEquals(2, dto.getComponentsToCover().size());
    }

    @Test
    @DisplayName("QuestionBank persistence and retrieval preserves rich details and topic")
    void testPersistenceAndDtoReconstruction() {
        UUID bankId = UUID.randomUUID();
        String sessionId = "sess-test-123";

        Question q1 = Question.builder()
                .id(sessionId + "_Q001")
                .questionType("technical")
                .difficulty("hard")
                .topic("PostgreSQL Indexing")
                .questionText("Giải thích B-Tree index và BRIN index?")
                .expectedAnswer("- Nêu rõ B-Tree phù hợp truy vấn exact match/range\n- BRIN phù hợp chuỗi dữ liệu sắp xếp liên tục")
                .details("""
                        {
                          "hints": ["Xem xét kích thước bảng lớn"],
                          "follow_up_questions": ["Khi nào nên dùng Partial Index?"],
                          "rationale": "Kiểm tra kiến thức DB chuyên sâu"
                        }
                        """)
                .build();

        Question q2 = Question.builder()
                .id(sessionId + "_Q002")
                .questionType("behavioural")
                .difficulty("medium")
                .topic("Team Conflict")
                .questionText("Hãy kể về lần bất đồng quan điểm kỹ thuật với Tech Lead?")
                .details("""
                        {
                          "star_prompt": "Áp dụng STAR để trả lời"
                        }
                        """)
                .build();

        QuestionBank bank = QuestionBank.builder()
                .id(bankId)
                .sessionId(sessionId)
                .questions(new ArrayList<>(List.of(q1, q2)))
                .build();

        when(questionBankRepo.findById(bankId)).thenReturn(Optional.of(bank));

        QuestionBankResponseDto response = service.getById(bankId);

        assertNotNull(response);
        assertEquals(2, response.getQuestionBank().size());

        QuestionDto dto1 = response.getQuestionBank().get(0);
        assertEquals("Q001", dto1.getId());
        assertEquals("PostgreSQL Indexing", dto1.getTopic());
        assertEquals("technical", dto1.getType());
        assertNotNull(dto1.getHints());
        assertEquals("Xem xét kích thước bảng lớn", dto1.getHints().get(0));
        assertNotNull(dto1.getFollowUpQuestions());
        assertEquals("Khi nào nên dùng Partial Index?", dto1.getFollowUpQuestions().get(0));
        assertEquals("Kiểm tra kiến thức DB chuyên sâu", dto1.getRationale());

        QuestionDto dto2 = response.getQuestionBank().get(1);
        assertEquals("Q002", dto2.getId());
        assertEquals("Team Conflict", dto2.getTopic());
        assertEquals("behavioural", dto2.getType());
        assertEquals("Áp dụng STAR để trả lời", dto2.getStarPrompt());
    }

    @Test
    @DisplayName("RegenerateQuestion matches short ID (Q001) against composite DB ID (sess_Q001)")
    void testRegenerateQuestionShortIdMatch() {
        UUID bankId = UUID.randomUUID();
        String sessionId = "sess-regen-456";

        Question q = Question.builder()
                .id(sessionId + "_Q001")
                .questionType("technical")
                .difficulty("medium")
                .topic("Old Topic")
                .questionText("Old Question Text")
                .expectedAnswer("Old Answer")
                .build();

        QuestionBank bank = QuestionBank.builder()
                .id(bankId)
                .sessionId(sessionId)
                .questions(new ArrayList<>(List.of(q)))
                .candidateContext(CandidateContextDto.builder()
                        .candidateLevel(SeniorityLevel.MID)
                        .roleType(JobCategory.BACKEND)
                        .build())
                .build();

        when(questionBankRepo.findById(bankId)).thenReturn(Optional.of(bank));

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.MID)
                .jobCategory(JobCategory.BACKEND)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        QuestionDto newQuestion = QuestionDto.builder()
                .question("New Regenerated Question Text")
                .evaluationCriteria("New Evaluation Criteria")
                .expectedCompetency("Java Concurrency")
                .topic("Concurrency")
                .hints(List.of("ReentrantLock", "AtomicInteger"))
                .build();

        when(questionGenerationService.regenerateSingle(
                eq("technical"), eq("medium"), any(), anyList(), anyList()
        )).thenReturn(newQuestion);

        when(questionBankRepo.save(any(QuestionBank.class))).thenAnswer(inv -> inv.getArgument(0));

        QuestionBankResponseDto response = service.regenerateQuestion(bankId, "Q001");

        assertNotNull(response);
        assertEquals(1, response.getQuestionBank().size());
        QuestionDto updatedDto = response.getQuestionBank().get(0);

        assertEquals("New Regenerated Question Text", updatedDto.getQuestion());
        assertEquals("New Evaluation Criteria", updatedDto.getEvaluationCriteria());
        assertEquals("Concurrency", updatedDto.getTopic());
        assertNotNull(updatedDto.getHints());
        assertEquals(2, updatedDto.getHints().size());
    }

    @Test
    @DisplayName("Redis Semantic Cache correctly groups and caches new questions mapped by itemId")
    void testRedisCacheWriting() {
        String sessionId = "sess-cache-789";

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.MID)
                .jobCategory(JobCategory.BACKEND)
                .overallMatchScore(85)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        EvidenceItemPair pair1 = new EvidenceItemPair(
                10L, "Spring Boot", "Spring Boot 3", "Spring Boot experience", "matched", "Strong", 10.0, "technical"
        );
        EvidenceItemPair pair2 = new EvidenceItemPair(
                20L, "Kubernetes", "K8s deployment", "No K8s found", "missing", "Gap", 10.0, "technical"
        );

        QuestionAssignment assign1 = new QuestionAssignment("technical", "hard", pair1, false, "drill-down");
        QuestionAssignment assign2 = new QuestionAssignment("technical", "easy", pair2, false, "conceptual");

        when(difficultyDistributor.distribute(any(QuestionConfigDto.class), any(), any(), anyList()))
                .thenReturn(List.of(assign1, assign2));

        when(cacheKeyGenerator.generateKey(eq(10L), eq("matched"), eq(SeniorityLevel.MID)))
                .thenReturn("siminterview:cache:item:10:matched:MID");
        when(cacheKeyGenerator.generateKey(eq(20L), eq("missing"), eq(SeniorityLevel.MID)))
                .thenReturn("siminterview:cache:item:20:missing:MID");

        when(cacheService.get(anyString())).thenReturn(null);

        QuestionDto genQ1 = QuestionDto.builder()
                .id("item_0")
                .type("technical")
                .difficulty("hard")
                .topic("Spring Boot Internals")
                .question("Cơ chế AutoConfiguration hoạt động như thế nào?")
                .build();

        QuestionDto genQ2 = QuestionDto.builder()
                .id("item_1")
                .type("technical")
                .difficulty("easy")
                .topic("K8s Basics")
                .question("Pod trong Kubernetes là gì?")
                .build();

        when(questionGenerationService.generateForCategory(eq("technical"), any(), anyList(), any()))
                .thenReturn(List.of(genQ1, genQ2));

        when(questionBankRepo.save(any(QuestionBank.class))).thenAnswer(inv -> {
            QuestionBank qb = inv.getArgument(0);
            qb.setId(UUID.randomUUID());
            return qb;
        });

        GenerateQuestionBankRequest request = GenerateQuestionBankRequest.builder()
                .sessionId(sessionId)
                .questionConfig(QuestionConfigDto.builder().total(2).build())
                .build();

        QuestionBankResponseDto response = service.generate(request);

        assertNotNull(response);
        assertEquals(2, response.getQuestionBank().size());

        verify(cacheService, times(1)).put(
                eq("siminterview:cache:item:10:matched:MID"),
                argThat(list -> list.size() == 1 && list.get(0).getQuestion().contains("AutoConfiguration")),
                eq(Duration.ofDays(7))
        );

        verify(cacheService, times(1)).put(
                eq("siminterview:cache:item:20:missing:MID"),
                argThat(list -> list.size() == 1 && list.get(0).getQuestion().contains("Pod trong Kubernetes")),
                eq(Duration.ofDays(7))
        );
    }

    @Test
    @DisplayName("detectTargetDomain accurately identifies domains in Vietnamese and English")
    void testDetectTargetDomain() {
        assertEquals("fintech", QuestionBankServiceImpl.detectTargetDomain("", "Tuyển lập trình viên Core Banking và Ví điện tử"));
        assertEquals("e-commerce", QuestionBankServiceImpl.detectTargetDomain("", "Xây dựng hệ thống sàn thương mại điện tử và giỏ hàng"));
        assertEquals("healthcare", QuestionBankServiceImpl.detectTargetDomain("", "Phát triển phần mềm quản lý bệnh viện và hồ sơ y tế"));
        assertEquals("edtech", QuestionBankServiceImpl.detectTargetDomain("", "Phát triển nền tảng giáo dục trực tuyến và khóa học"));
        assertEquals("logistics", QuestionBankServiceImpl.detectTargetDomain("", "Hệ thống quản lý kho bãi, vận tải và giao nhận"));
        assertEquals("ai_data", QuestionBankServiceImpl.detectTargetDomain("", "Xây dựng mô hình trí tuệ nhân tạo và kho dữ liệu lớn"));
        assertEquals("saas", QuestionBankServiceImpl.detectTargetDomain("", "Multi-tenant cloud SaaS platform with billing"));
    }

    @Test
    @DisplayName("Cache Deduplication prevents duplicate questions when multiple assignments hit same cache key")
    void testCacheDeduplication() {
        String sessionId = "sess-dedup-101";

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.MID)
                .jobCategory(JobCategory.BACKEND)
                .overallMatchScore(80)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        EvidenceItemPair pair = new EvidenceItemPair(
                55L, "Java Core", "Java knowledge", "Java 5 years", "matched", "Strong", 10.0, "technical"
        );

        QuestionAssignment assign1 = new QuestionAssignment("technical", "medium", pair, false, "drill-down");
        QuestionAssignment assign2 = new QuestionAssignment("technical", "medium", pair, false, "drill-down");

        when(difficultyDistributor.distribute(any(QuestionConfigDto.class), any(), any(), anyList()))
                .thenReturn(List.of(assign1, assign2));

        when(cacheKeyGenerator.generateKey(eq(55L), eq("matched"), eq(SeniorityLevel.MID)))
                .thenReturn("siminterview:cache:item:55:matched:MID");

        QuestionDto cachedQ1 = QuestionDto.builder()
                .type("technical")
                .difficulty("medium")
                .question("Java Memory Model hoạt động ra sao?")
                .build();

        when(cacheService.get(eq("siminterview:cache:item:55:matched:MID")))
                .thenReturn(List.of(cachedQ1));

        QuestionDto genQ2 = QuestionDto.builder()
                .id("item_0")
                .type("technical")
                .difficulty("medium")
                .topic("Java Generics")
                .question("Type Erasure trong Java Generics là gì?")
                .build();

        when(questionGenerationService.generateForCategory(eq("technical"), any(), anyList(), any()))
                .thenReturn(List.of(genQ2));

        when(questionBankRepo.save(any(QuestionBank.class))).thenAnswer(inv -> {
            QuestionBank qb = inv.getArgument(0);
            qb.setId(UUID.randomUUID());
            return qb;
        });

        GenerateQuestionBankRequest request = GenerateQuestionBankRequest.builder()
                .sessionId(sessionId)
                .questionConfig(QuestionConfigDto.builder().total(2).build())
                .build();

        QuestionBankResponseDto response = service.generate(request);

        assertNotNull(response);
        assertEquals(2, response.getQuestionBank().size());

        String qText1 = response.getQuestionBank().get(0).getQuestion();
        String qText2 = response.getQuestionBank().get(1).getQuestion();

        assertNotEquals(qText1, qText2, "The two questions in the bank must be distinct!");
        assertTrue(qText1.contains("Java Memory Model") || qText2.contains("Java Memory Model"));
        assertTrue(qText1.contains("Type Erasure") || qText2.contains("Type Erasure"));
    }

    @Test
    @DisplayName("QuestionBank clamping restricts totalQuestions between 10 and 30")
    void testTotalQuestionsClamping() {
        String sessionId = "sess-clamp-1";

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.MID)
                .jobCategory(JobCategory.BACKEND)
                .overallMatchScore(80)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        when(difficultyDistributor.distribute(any(QuestionConfigDto.class), any(), any(), anyList()))
                .thenAnswer(inv -> {
                    QuestionConfigDto cfg = inv.getArgument(0);
                    assertEquals(30, cfg.getTotalQuestions(), "Over-limit request of 100 must be clamped to 30");
                    return Collections.emptyList();
                });

        GenerateQuestionBankRequest requestOver = GenerateQuestionBankRequest.builder()
                .sessionId(sessionId)
                .questionConfig(QuestionConfigDto.builder().total(100).build())
                .build();

        assertThrows(QuestionBankException.class, () -> service.generate(requestOver));
    }

    @Test
    @DisplayName("Graceful Degradation: If one category fails, others still succeed and are returned")
    void testGracefulDegradationOnPartialCategoryFailure() {
        String sessionId = "sess-partial-fail-1";

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.MID)
                .jobCategory(JobCategory.BACKEND)
                .overallMatchScore(80)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        EvidenceItemPair pair1 = new EvidenceItemPair(1L, "Java", "Java req", "Java exp", "matched", "Good", 10.0, "technical");
        EvidenceItemPair pair2 = new EvidenceItemPair(2L, "Teamwork", "Team req", "Team exp", "matched", "Good", 10.0, "behavioural");

        QuestionAssignment assignTech = new QuestionAssignment("technical", "medium", pair1, false, "drill-down");
        QuestionAssignment assignBehav = new QuestionAssignment("behavioural", "medium", pair2, false, "star");

        when(difficultyDistributor.distribute(any(QuestionConfigDto.class), any(), any(), anyList()))
                .thenReturn(List.of(assignTech, assignBehav));

        when(cacheKeyGenerator.generateKey(anyLong(), anyString(), any()))
                .thenReturn("siminterview:cache:test");
        when(cacheService.get(anyString())).thenReturn(null);

        QuestionDto techQ = QuestionDto.builder()
                .id("item_0")
                .type("technical")
                .difficulty("medium")
                .question("Java Concurrency hoạt động như thế nào?")
                .build();

        // Technical succeeds
        when(questionGenerationService.generateForCategory(eq("technical"), any(), anyList(), any()))
                .thenReturn(List.of(techQ));

        // Behavioural fails with exception
        when(questionGenerationService.generateForCategory(eq("behavioural"), any(), anyList(), any()))
                .thenThrow(new RuntimeException("LLM API Timeout for behavioural category"));

        when(questionBankRepo.save(any(QuestionBank.class))).thenAnswer(inv -> {
            QuestionBank qb = inv.getArgument(0);
            qb.setId(UUID.randomUUID());
            return qb;
        });

        GenerateQuestionBankRequest request = GenerateQuestionBankRequest.builder()
                .sessionId(sessionId)
                .questionConfig(QuestionConfigDto.builder().total(2).build())
                .build();

        QuestionBankResponseDto response = service.generate(request);

        assertNotNull(response);
        assertEquals(1, response.getQuestionBank().size(), "Should gracefully return the 1 technical question that succeeded");
        assertEquals("technical", response.getQuestionBank().get(0).getType());
    }

    @Test
    @DisplayName("extractProjectHighlights correctly extracts project summaries and bullets from CV")
    void testExtractProjectHighlights() {
        String cv = """
                # Nguyen Van A - Senior Backend Developer
                
                ## KINH NGHIỆM LÀM VIỆC & DỰ ÁN
                - Payment Gateway Platform: Xử lý 15.000 RPS với Redis Lock và PostgreSQL Partitioning.
                - Real-time Chat Microservices: Xây dựng hệ thống WebSocket chịu tải 100k kết nối đồng thời.
                - Giảm độ trễ hệ thống từ 450ms xuống 45ms bằng cách tối ưu hoá Cache Strategy.
                """;

        List<String> highlights = QuestionBankServiceImpl.extractProjectHighlights(cv);
        assertNotNull(highlights);
        assertFalse(highlights.isEmpty());
        assertTrue(highlights.stream().anyMatch(h -> h.contains("Payment Gateway")));
        assertTrue(highlights.stream().anyMatch(h -> h.contains("15.000 RPS")));
    }

    @Test
    @DisplayName("DEEP_DIVE mode bypasses Redis Cache and generates project-anchored questions")
    void testDeepDiveModeBypassesCache() {
        String sessionId = "sess-deep-dive-1";

        ResumeAssessment assessment = ResumeAssessment.builder()
                .id(UUID.randomUUID())
                .sessionId(sessionId)
                .seniorityLevel(SeniorityLevel.SENIOR)
                .jobCategory(JobCategory.BACKEND)
                .overallMatchScore(90)
                .evidenceItems(Collections.emptyList())
                .build();

        when(assessmentRepo.findBySessionId(sessionId)).thenReturn(Optional.of(assessment));
        when(evaluationCriteriaRepository.findAll()).thenReturn(Collections.emptyList());

        EvidenceItemPair pair = new EvidenceItemPair(
                1L, "Spring Boot", "Spring Boot required", "Spring Boot 5y exp", "matched", "Strong", 10.0, "technical"
        );
        QuestionAssignment assign = new QuestionAssignment("technical", "hard", pair, false, "drill-down");

        when(difficultyDistributor.distribute(any(QuestionConfigDto.class), any(), any(), anyList()))
                .thenReturn(List.of(assign));

        QuestionDto deepDiveQ = QuestionDto.builder()
                .id("item_0")
                .type("technical")
                .difficulty("hard")
                .topic("Payment System Concurrency")
                .question("Trong dự án Payment Gateway, bạn đã xử lý race condition khi 2 request trừ tiền đồng thời như thế nào?")
                .build();

        when(questionGenerationService.generateForCategory(eq("technical"), any(), anyList(), any()))
                .thenReturn(List.of(deepDiveQ));

        when(questionBankRepo.save(any(QuestionBank.class))).thenAnswer(inv -> {
            QuestionBank qb = inv.getArgument(0);
            qb.setId(UUID.randomUUID());
            return qb;
        });

        GenerateQuestionBankRequest request = GenerateQuestionBankRequest.builder()
                .sessionId(sessionId)
                .questionConfig(QuestionConfigDto.builder()
                        .total(1)
                        .mode("DEEP_DIVE")
                        .interviewChannel("VOICE")
                        .build())
                .build();

        QuestionBankResponseDto response = service.generate(request);

        assertNotNull(response);
        assertEquals(1, response.getQuestionBank().size());
        assertEquals("Payment System Concurrency", response.getQuestionBank().get(0).getTopic());

        // Verify cacheService.get was NOT called because DEEP_DIVE bypasses generic cache
        verify(cacheService, never()).get(anyString());
        // Verify cacheService.put was NOT called for deep dive questions
        verify(cacheService, never()).put(anyString(), anyList(), any());
    }
}
