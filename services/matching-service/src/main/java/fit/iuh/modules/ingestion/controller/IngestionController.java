package fit.iuh.modules.ingestion.controller;

import fit.iuh.modules.ingestion.dto.IngestionResponse;
import fit.iuh.modules.ingestion.service.IngestionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final IngestionService ingestionService;

    @PostMapping(
            value = "/{sessionId}",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    public ResponseEntity<IngestionResponse> ingest(
            @PathVariable String sessionId,
            @RequestPart(value = "cvFile", required = false) MultipartFile cvFile,
            @RequestPart(value = "jdFile", required = false) MultipartFile jdFile,
            @RequestPart(value = "jdText", required = false) String jdText,
            @RequestPart(value = "resumeMarkdown", required = false) String resumeMarkdown,
            @RequestPart(value = "jdMarkdown", required = false) String jdMarkdown) {

        log.info("Received ingestion request: sessionId={}, cvFile={}, jdFile={}",
                sessionId,
                cvFile != null ? cvFile.getOriginalFilename() : "null",
                jdFile != null ? jdFile.getOriginalFilename() : "null");

        IngestionResponse response = ingestionService.ingest(
                sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown);

        return ResponseEntity.ok(response);
    }



    @DeleteMapping("/{sessionId}")
    public ResponseEntity<java.util.Map<String, String>> deleteSession(@PathVariable String sessionId) {
        log.info("Received request to delete session: {}", sessionId);
        ingestionService.deleteSession(sessionId);
        return ResponseEntity.ok(java.util.Map.of(
                "sessionId", sessionId,
                "message", "Session documents and chunks deleted successfully."
        ));
    }
}
