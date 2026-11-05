package fit.iuh.modules.ingestion.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class IngestionResponse {

    private String sessionId;
    private String status;
    private String message;
    private String cvMarkdown;
    private String jdMarkdown;
    private String rawCvText;
    private String rawJdText;
}
