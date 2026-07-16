package fit.iuh.modules.assessment;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import fit.iuh.config.PromptTemplateConfig;
import fit.iuh.dto.chat.LlmChatRequest;
import fit.iuh.dto.chat.LlmChatResponse;
import fit.iuh.config.AppProperties;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
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
public class GateExtractionService {

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
        public DateRange(LocalDate start, LocalDate end) {
            this.start = start;
            this.end = end;
        }
    }

    public Eligibility evaluateEligibility(String jdMarkdown, String cvMarkdown) {
        // 1. Extract and Evaluate GATE requirements from LLM (using JD + CV)
        List<GateCheckDto> gateReqs = extractAndEvaluateGateRequirements(jdMarkdown, cvMarkdown);
        if (gateReqs == null || gateReqs.isEmpty()) {
            return Eligibility.builder()
                    .status(EligibilityStatus.ELIGIBLE)
                    .gateChecks(List.of())
                    .build();
        }

        // 2. Parse candidate CV for YOE
        double candidateYoe = calculateCandidateYoe(cvMarkdown);
        
        // 3. Evaluate each gate
        List<GateCheck> checks = new ArrayList<>();
        boolean allRequiredMet = true;
        boolean allPreferredMet = true;
        
        for (GateCheckDto req : gateReqs) {
            Importance imp = Importance.PREFERRED;
            if (req.getImportance() != null && req.getImportance().toUpperCase().contains("REQUIRED")) {
                imp = Importance.REQUIRED;
            }

            GateCheck check = GateCheck.builder()
                    .criteriaName(req.getCriteriaName())
                    .importance(imp)
                    .requiredValue(req.getRequiredValue())
                    .actualValue(req.getActualValue() != null ? req.getActualValue() : "Not evaluated")
                    .status(req.getStatus() != null ? req.getStatus().toLowerCase() : "not_met")
                    .build();

            // Override GPA importance based on config
            if (check.getCriteriaName() != null && check.getCriteriaName().toLowerCase().contains("gpa")) {
                check.setImportance(defaultGpaImportance);
            }

            // Java Override: Enforce deterministic rules for YOE and GPA
            overrideGateCheck(check, candidateYoe, cvMarkdown);
            checks.add(check);

            if (check.getImportance() == Importance.REQUIRED && "not_met".equals(check.getStatus())) {
                allRequiredMet = false;
            } else if (check.getImportance() == Importance.PREFERRED && "not_met".equals(check.getStatus())) {
                allPreferredMet = false;
            }
        }

        // 4. Calculate overall status
        EligibilityStatus overallStatus;
        if (!allRequiredMet) {
            overallStatus = EligibilityStatus.NOT_ELIGIBLE;
        } else if (!allPreferredMet) {
            overallStatus = EligibilityStatus.PARTIAL;
        } else {
            overallStatus = EligibilityStatus.ELIGIBLE;
        }

        return Eligibility.builder()
                .status(overallStatus)
                .gateChecks(checks)
                .build();
    }

    private List<GateCheckDto> extractAndEvaluateGateRequirements(String jdMarkdown, String cvMarkdown) {
        String userPrompt = "====== JOB DESCRIPTION ======\n" + jdMarkdown + "\n\n====== CANDIDATE CV ======\n" + cvMarkdown;
        LlmChatRequest request = LlmChatRequest.builder()
                .model(appProperties.getLlm().getModel())
                .stream(false)
                .temperature(0.1)
                .responseFormat(java.util.Map.of("type", "json_object"))
                .messages(List.of(
                        LlmChatRequest.Message.system(PromptTemplateConfig.SYSTEM_PROMPT_GATE_EXTRACTION),
                        LlmChatRequest.Message.user(userPrompt)
                ))
                .build();
                
        try {
            String responseBody = llmWebClient.post()
                    .uri(llmChatPath)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
            
            LlmChatResponse response = objectMapper.readValue(responseBody, LlmChatResponse.class);
            String json = response.getFirstChoiceContent().replaceAll("(?s)^```json\\s*", "").replaceAll("(?s)\\s*```$", "").strip();
            GateExtractionDto dto = objectMapper.readValue(json, GateExtractionDto.class);
            return dto.getGateRequirements() != null ? dto.getGateRequirements() : List.of();
        } catch (Exception e) {
            log.error("[GateExtraction] Failed to extract GATE from JD: {}", e.getMessage(), e);
            return List.of();
        }
    }

    private void overrideGateCheck(GateCheck check, double candidateYoe, String cvMarkdown) {
        String name = check.getCriteriaName().toLowerCase();
        if (name.contains("year") || name.contains("yoe") || name.contains("kinh nghiệm") || name.contains("experience")) {
            // Try to extract required number
            double reqYoe = extractNumber(check.getRequiredValue());
            boolean isTextualReq = !check.getRequiredValue().matches(".*\\d.*");

            if (!isTextualReq) {
                check.setActualValue(candidateYoe + " years");
                if (reqYoe >= 0) {
                    check.setStatus(candidateYoe >= reqYoe ? "met" : "not_met");
                } else {
                    check.setStatus("not_met"); // Cannot parse required YOE
                }
            } else {
                 // For purely textual requirements (e.g. "Final year student"), trust the LLM reasoning
                 // Do not override actual_value and status.
            }
        } else if (name.contains("gpa")) {
            double reqGpa = extractNumber(check.getRequiredValue());
            double candidateGpa = extractGpa(cvMarkdown);
            
            if (candidateGpa >= 0) {
                check.setActualValue(String.valueOf(candidateGpa));
                if (reqGpa >= 0) {
                    check.setStatus(candidateGpa >= reqGpa ? "met" : "not_met");
                } else {
                    check.setStatus("met"); // Has GPA but required value unclear
                }
            } else {
                check.setActualValue("Not found in CV");
                check.setStatus("not_met");
            }
        }
        // For Education, Certifications, etc. -> Keep the LLM evaluated values!
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
        // Extract the # Experience block
        int expIdx = cvMarkdown.indexOf("# Experience");
        if (expIdx == -1) return 0.0;
        
        int nextSectionIdx = cvMarkdown.indexOf("\n# ", expIdx + 5);
        String expSection = nextSectionIdx == -1 ? cvMarkdown.substring(expIdx) : cvMarkdown.substring(expIdx, nextSectionIdx);

        // Pattern for dates: Jan 2020 - Dec 2021 | 01/2020 - Present
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
            // Attempt standard formats
            if (dateStr.matches(".*[a-zA-Z]+.*")) {
                // e.g. Jan 2020
                String[] parts = dateStr.trim().split("[-/\\s]+");
                if (parts.length >= 2) {
                    int month = parseMonth(parts[0]);
                    int year = Integer.parseInt(parts[1]);
                    if (year < 100) year += 2000;
                    return LocalDate.of(year, month, 1);
                }
            } else {
                // e.g. 01/2020
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
