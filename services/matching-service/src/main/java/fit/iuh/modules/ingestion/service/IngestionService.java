package fit.iuh.modules.ingestion.service;

import fit.iuh.modules.ingestion.dto.IngestionResponse;
import org.springframework.web.multipart.MultipartFile;

public interface IngestionService {

    IngestionResponse ingest(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown);

    void deleteSession(String sessionId);
}
