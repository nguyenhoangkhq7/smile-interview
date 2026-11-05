package fit.iuh.modules.ingestion.service;

import org.springframework.web.multipart.MultipartFile;

public interface PdfService {
    String extractText(MultipartFile file);
}
