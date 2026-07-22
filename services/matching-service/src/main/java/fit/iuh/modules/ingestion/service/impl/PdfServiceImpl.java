package fit.iuh.modules.ingestion.service.impl;

import fit.iuh.exception.PdfParsingException;
import fit.iuh.modules.ingestion.service.PdfService;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

@Slf4j
@Service
public class PdfServiceImpl implements PdfService {

    private static final String PDF_MIME_TYPE = "application/pdf";
    private static final int MIN_TEXT_LENGTH = 50;

    @Override
    public String extractText(MultipartFile file) {
        validateFile(file);

        log.debug("Extracting text from PDF: name='{}', size={}KB",
                file.getOriginalFilename(), file.getSize() / 1024);

        try (InputStream inputStream = file.getInputStream();
             PDDocument document = Loader.loadPDF(new RandomAccessReadBuffer(inputStream))) {

            if (document.isEncrypted()) {
                throw new PdfParsingException(
                        "The uploaded PDF '" + file.getOriginalFilename() +
                        "' is password-protected. Please upload an unencrypted PDF.");
            }

            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);

            String rawText = stripper.getText(document);

            if (rawText == null || rawText.strip().length() < MIN_TEXT_LENGTH) {
                throw new PdfParsingException(
                        "Insufficient text extracted from '" + file.getOriginalFilename() + "'. " +
                        "The PDF may contain only scanned images (no embedded text layer). " +
                        "Please provide a text-selectable PDF.");
            }

            String cleaned = cleanText(rawText);
            log.debug("PDF text extraction complete: {} chars from '{}'",
                    cleaned.length(), file.getOriginalFilename());
            return cleaned;

        } catch (PdfParsingException e) {
            throw e;
        } catch (IOException e) {
            throw new PdfParsingException(
                    "IO error reading PDF '" + file.getOriginalFilename() + "': " + e.getMessage(), e);
        } catch (Exception e) {
            throw new PdfParsingException(
                    "Unexpected error parsing PDF '" + file.getOriginalFilename() + "': " + e.getMessage(), e);
        }
    }

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new PdfParsingException("Uploaded PDF file cannot be null or empty.");
        }

        String filename = file.getOriginalFilename();
        if (filename == null || !filename.toLowerCase().endsWith(".pdf")) {
            throw new PdfParsingException(
                    "Invalid file extension for '" + filename + "'. Only .pdf files are supported.");
        }

        String contentType = file.getContentType();
        if (contentType != null && !contentType.equalsIgnoreCase(PDF_MIME_TYPE) &&
            !contentType.equalsIgnoreCase("application/x-pdf")) {
            log.warn("Non-standard PDF MIME type reported by client: '{}' for file '{}'. Attempting parse anyway.",
                    contentType, filename);
        }
    }

    private String cleanText(String rawText) {
        return rawText
                .replaceAll("\r\n", "\n")
                .replaceAll("\r", "\n")
                .replaceAll("\n{3,}", "\n\n")
                .strip();
    }
}
