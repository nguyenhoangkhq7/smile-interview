package fit.iuh.modules.ingestion.service;

import fit.iuh.modules.auth.entity.User;
import fit.iuh.modules.ingestion.dto.IngestionResponse;
import org.springframework.web.multipart.MultipartFile;

public interface IngestionService {

    default IngestionResponse ingest(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown,
            String jdCategory,
            String jdAcceptedLevels,
            String cvCategory,
            String cvSeniorityLevel) {
        return ingest(sessionId, cvFile, jdFile, jdText, resumeMarkdown, jdMarkdown,
                jdCategory, jdAcceptedLevels, cvCategory, cvSeniorityLevel, null, null, null);
    }

    IngestionResponse ingest(
            String sessionId,
            MultipartFile cvFile,
            MultipartFile jdFile,
            String jdText,
            String resumeMarkdown,
            String jdMarkdown,
            String jdCategory,
            String jdAcceptedLevels,
            String cvCategory,
            String cvSeniorityLevel,
            String roleTitle,
            String interviewType,
            User currentUser);

    void deleteSession(String sessionId);
}
