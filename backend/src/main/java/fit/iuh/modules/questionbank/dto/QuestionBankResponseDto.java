package fit.iuh.modules.questionbank.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuestionBankResponseDto {

    @JsonProperty("id")
    private UUID id;

    @JsonProperty("session_id")
    private String sessionId;

    @JsonProperty("metadata")
    private QuestionBankMetadataDto metadata;

    @JsonProperty("question_bank")
    private List<QuestionDto> questionBank;

    @JsonProperty("created_at")
    private LocalDateTime createdAt;
}
