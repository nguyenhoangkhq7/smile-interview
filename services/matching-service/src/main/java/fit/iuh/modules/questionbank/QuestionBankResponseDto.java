package fit.iuh.modules.questionbank;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * Top-level API response wrapping the question bank metadata and the
 * full list of generated questions.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuestionBankResponseDto {

    private UUID id;

    @JsonProperty("session_id")
    private String sessionId;

    private QuestionBankMetadataDto metadata;

    @JsonProperty("question_bank")
    private List<QuestionDto> questionBank;

    @JsonProperty("created_at")
    private LocalDateTime createdAt;
}
