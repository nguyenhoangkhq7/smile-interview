package fit.iuh.modules.ingestion.service;

public interface StandardizationService {
    String standardizeCv(String rawCvText);
    String standardizeJd(String rawJdText);
}
