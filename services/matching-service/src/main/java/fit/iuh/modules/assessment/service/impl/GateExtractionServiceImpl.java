package fit.iuh.modules.assessment.service.impl;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.AppProperties;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.modules.assessment.entity.Eligibility;
import fit.iuh.modules.assessment.entity.EligibilityStatus;
import fit.iuh.modules.assessment.entity.GateCheck;
import fit.iuh.modules.assessment.entity.Importance;
import fit.iuh.modules.assessment.prompt.AssessmentPrompts;
import fit.iuh.modules.assessment.service.GateExtractionService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@Slf4j
@RequiredArgsConstructor
public class GateExtractionServiceImpl implements GateExtractionService {

    private final WebClient llmWebClient;
    private final ObjectMapper objectMapper;
    private final AppProperties appProperties;

    @Value("${app.llm.chat-path:/v1/chat/completions}")
    private String llmChatPath;

    @Value("${app.assessment.gate.gpa.default-importance:PREFERRED}")
    private Importance defaultGpaImportance;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class GateExtractionDto {
        @JsonProperty("gate_requirements")
        private List<GateCheckDto> gateRequirements;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class GateCheckDto {
        @JsonProperty("criteria_name")
        private String criteriaName;
        @JsonProperty("importance")
        private String importance;
        @JsonProperty("required_value")
        private String requiredValue;
        @JsonProperty("actual_value")
        private String actualValue;
        @JsonProperty("status")
        private String status;
    }

    private static class DateRange {
        LocalDate start;
        LocalDate end;

        DateRange(LocalDate start, LocalDate end) {
            this.start = start;
            this.end = end;
        }
    }

    @Override
    public Eligibility evaluateEligibility(String jdContent, String cvContent) {
        log.info("[GateExtraction] Extracting GATE requirements from JD...");
        List<GateCheckDto> rawGates = null;
        boolean extractionFailed = false;

        try {
            rawGates = extractGateFromJd(jdContent, cvContent);
        } catch (Exception e) {
            log.error("[GateExtraction] Extraction threw exception, marking evaluation UNCERTAIN: {}", e.getMessage());
            extractionFailed = true;
        }

        if (extractionFailed || rawGates == null) {
            log.warn("[GateExtraction] LLM extraction failed. Gracefully falling back to UNCERTAIN status for manual review.");
            return Eligibility.builder()
                    .status(EligibilityStatus.UNCERTAIN)
                    .gateChecks(List.of())
                    .build();
        }

        double candidateYoe = calculateCandidateYoe(cvContent);
        log.info("[GateExtraction] Calculated Candidate YOE: {} years", candidateYoe);

        List<GateCheck> checks = new ArrayList<>();
        boolean isEligible = true;

        for (GateCheckDto dto : rawGates) {
            Importance imp = Importance.REQUIRED;
            if (dto.getImportance() != null) {
                try {
                    imp = Importance.valueOf(dto.getImportance().toUpperCase());
                } catch (Exception ignored) {}
            }

            GateCheck check = GateCheck.builder()
                    .criteriaName(dto.getCriteriaName())
                    .importance(imp)
                    .requiredValue(dto.getRequiredValue())
                    .actualValue(dto.getActualValue())
                    .status(dto.getStatus())
                    .build();

            overrideGateCheck(check, candidateYoe, cvContent);

            if (check.getImportance() == Importance.REQUIRED && "not_met".equalsIgnoreCase(check.getStatus())) {
                isEligible = false;
            }

            checks.add(check);
        }

        EligibilityStatus status = isEligible ? EligibilityStatus.ELIGIBLE : EligibilityStatus.NOT_ELIGIBLE;
        log.info("[GateExtraction] Final Evaluation: Status={}, Total Checks={}", status, checks.size());

        return Eligibility.builder()
                .status(status)
                .gateChecks(checks)
                .build();
    }

    private List<GateCheckDto> extractGateFromJd(String jdMarkdown, String cvMarkdown) {
        String userPrompt = "====== JOB DESCRIPTION ======\n" + jdMarkdown + "\n\n====== CANDIDATE CV ======\n" + cvMarkdown;

        LlmChatRequest requestWithFormat = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .stream(false)
                .temperature(0.1)
                .responseFormat(java.util.Map.of("type", "json_object"))
                .messages(List.of(
                        LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_GATE_EXTRACTION),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();

        String responseBody = null;
        try {
            responseBody = llmWebClient.post()
                    .uri(llmChatPath)
                    .bodyValue(requestWithFormat)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
        } catch (org.springframework.web.reactive.function.client.WebClientResponseException.BadRequest ex) {
            log.warn("[GateExtraction] Model '{}' rejected response_format (400 Bad Request). Retrying without response_format...", appProperties.getLlm().getModel());
            LlmChatRequest fallbackRequest = LlmChatRequest.builder()
                    .model(appProperties.getLlm().getModel())
                    .stream(false)
                    .temperature(0.1)
                    .messages(List.of(
                            LlmChatRequest.Message.system(AssessmentPrompts.SYSTEM_PROMPT_GATE_EXTRACTION),
                            LlmChatRequest.Message.user(userPrompt)
                    ))
                    .build();

            responseBody = llmWebClient.post()
                    .uri(llmChatPath)
                    .bodyValue(fallbackRequest)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
        } catch (Exception e) {
            log.error("[GateExtraction] Failed to extract GATE from JD: {}", e.getMessage(), e);
            throw e;
        }

        try {
            LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
            String rawContent = response.getFirstChoiceContent();
            String json = rawContent.replaceAll("(?s)^```(?:json)?\\s*", "").replaceAll("(?s)\\s*```$", "").strip();
            GateExtractionDto dto = objectMapper.readValue(json, GateExtractionDto.class);
            return dto.getGateRequirements() != null ? dto.getGateRequirements() : List.of();
        } catch (Exception e) {
            log.error("[GateExtraction] Parsing GATE extraction response failed: {}", e.getMessage());
            throw new RuntimeException("Failed to parse LLM Gate response", e);
        }
    }

    private void overrideGateCheck(GateCheck check, double candidateYoe, String cvMarkdown) {
        String name = check.getCriteriaName().toLowerCase();
        if (name.contains("year") || name.contains("yoe") || name.contains("kinh nghiệm") || name.contains("experience")) {
            double reqYoe = extractNumber(check.getRequiredValue());
            boolean isTextualReq = !check.getRequiredValue().matches(".*\\d.*");

            if (!isTextualReq) {
                check.setActualValue(candidateYoe + " years");
                if (reqYoe >= 0) {
                    check.setStatus(candidateYoe >= reqYoe ? "met" : "not_met");
                } else {
                    check.setStatus("not_met");
                }
            }
        } else if (name.contains("gpa")) {
            double reqGpa = extractNumber(check.getRequiredValue());
            double candidateGpa = extractGpa(cvMarkdown);

            if (candidateGpa >= 0) {
                check.setActualValue(String.valueOf(candidateGpa));
                if (reqGpa >= 0) {
                    check.setStatus(candidateGpa >= reqGpa ? "met" : "not_met");
                } else {
                    check.setStatus("met");
                }
            } else {
                check.setActualValue("Not found in CV");
                check.setStatus("not_met");
            }
        }
    }

    private double extractNumber(String text) {
        if (text == null) return -1;

        String lower = text.toLowerCase();
        if (lower.matches(".*(fresher|student|graduate|sinh viên|mới ra trường|mới tốt nghiệp).*")) {
            return 0.0;
        }

        Pattern p = Pattern.compile("(\\d+(\\.\\d+)?)");
        Matcher m = p.matcher(text);
        if (m.find()) {
            try {
                return Double.parseDouble(m.group(1));
            } catch (Exception ignored) {}
        }
        return -1;
    }

    private double extractGpa(String cvMarkdown) {
        Pattern p = Pattern.compile("GPA:\\s*(\\d+(\\.\\d+)?)", Pattern.CASE_INSENSITIVE);
        Matcher m = p.matcher(cvMarkdown);
        if (m.find()) {
            try {
                return Double.parseDouble(m.group(1));
            } catch (Exception ignored) {}
        }
        return -1;
    }

    public double calculateCandidateYoe(String cvMarkdown) {
        int expIdx = cvMarkdown.indexOf("# Experience");
        if (expIdx == -1) return 0.0;

        int nextSectionIdx = cvMarkdown.indexOf("\n# ", expIdx + 5);
        String expSection = nextSectionIdx == -1 ? cvMarkdown.substring(expIdx) : cvMarkdown.substring(expIdx, nextSectionIdx);

        Pattern datePattern = Pattern.compile("((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[0-9]{1,2})[-/\\s]+[0-9]{4})\\s*[-–to]+\\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[0-9]{1,2})[-/\\s]+[0-9]{4}|Present|Nay|Hiện tại)", Pattern.CASE_INSENSITIVE);
        Matcher m = datePattern.matcher(expSection);

        List<DateRange> ranges = new ArrayList<>();
        while (m.find()) {
            LocalDate start = parseDate(m.group(1));
            LocalDate end = m.group(2).toLowerCase().matches("present|nay|hiện tại") ? LocalDate.now() : parseDate(m.group(2));
            if (start != null && end != null && !start.isAfter(end)) {
                ranges.add(new DateRange(start, end));
            }
        }

        if (ranges.isEmpty()) return 0.0;

        ranges.sort(Comparator.comparing(r -> r.start));
        List<DateRange> merged = new ArrayList<>();
        DateRange current = new DateRange(ranges.get(0).start, ranges.get(0).end);

        for (int i = 1; i < ranges.size(); i++) {
            DateRange next = ranges.get(i);
            if (!next.start.isAfter(current.end)) {
                if (next.end.isAfter(current.end)) {
                    current.end = next.end;
                }
            } else {
                merged.add(current);
                current = new DateRange(next.start, next.end);
            }
        }
        merged.add(current);

        long totalDays = 0;
        for (DateRange r : merged) {
            totalDays += ChronoUnit.DAYS.between(r.start, r.end) + 1;
        }

        double yoe = totalDays / 365.25;
        return Math.round(yoe * 100.0) / 100.0;
    }

    private LocalDate parseDate(String dateStr) {
        try {
            if (dateStr.matches(".*[a-zA-Z]+.*")) {
                String[] parts = dateStr.trim().split("[-/\\s]+");
                if (parts.length >= 2) {
                    int month = parseMonth(parts[0]);
                    int year = Integer.parseInt(parts[1]);
                    if (year < 100) year += 2000;
                    return LocalDate.of(year, month, 1);
                }
            } else {
                String[] parts = dateStr.trim().split("[-/\\s]+");
                if (parts.length >= 2) {
                    int month = Integer.parseInt(parts[0]);
                    int year = Integer.parseInt(parts[1]);
                    if (year < 100) year += 2000;
                    return LocalDate.of(year, month, 1);
                }
            }
        } catch (Exception e) {
            log.debug("Failed to parse date: {}", dateStr);
        }
        return null;
    }

    private int parseMonth(String m) {
        m = m.toLowerCase();
        if (m.startsWith("jan")) return 1;
        if (m.startsWith("feb")) return 2;
        if (m.startsWith("mar")) return 3;
        if (m.startsWith("apr")) return 4;
        if (m.startsWith("may")) return 5;
        if (m.startsWith("jun")) return 6;
        if (m.startsWith("jul")) return 7;
        if (m.startsWith("aug")) return 8;
        if (m.startsWith("sep")) return 9;
        if (m.startsWith("oct")) return 10;
        if (m.startsWith("nov")) return 11;
        if (m.startsWith("dec")) return 12;
        return 1;
    }
}
