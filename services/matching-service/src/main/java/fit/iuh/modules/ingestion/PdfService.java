package fit.iuh.modules.ingestion;

import fit.iuh.exception.PdfParsingException;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

/**
 * Service responsible for extracting plain text from uploaded PDF files
 * using Apache PDFBox 3.x.
 *
 * <p><strong>PDFBox 3.x API change:</strong> The static factory method
 * {@code PDDocument.load(InputStream)} was removed in PDFBox 3.0.
 * The correct API is now:
 * <pre>
 *   Loader.loadPDF(new RandomAccessReadBuffer(inputStream));
 * </pre>
 *
 * <p>Handles the following error scenarios gracefully:
 * <ul>
 *   <li>Null or empty {@link MultipartFile}</li>
 *   <li>Non-PDF MIME type (wrong file type)</li>
 *   <li>Password-protected (encrypted) PDF</li>
 *   <li>Scanned image-only PDFs (no embedded text layer)</li>
 *   <li>Corrupted or unreadable PDF data</li>
 * </ul>
 *
 * <p>All failures throw {@link PdfParsingException} → HTTP 400 via
 * {@link fit.iuh.exception.GlobalExceptionHandler}.
 */
@Slf4j
@Service
public class PdfService {

    private static final String PDF_MIME_TYPE  = "application/pdf";
    private static final int    MIN_TEXT_LENGTH = 50; // characters

    /**
     * Extracts all readable text from an uploaded PDF file.
     *
     * <p>Uses {@link PDFTextStripper} with sort-by-position enabled for accurate
     * text ordering in multi-column layouts. The extracted text is then lightly
     * cleaned (line endings normalized, excessive blank lines collapsed).
     *
     * @param file the uploaded multipart PDF file (must not be null or empty)
     * @return extracted plain text; never blank (validated)
     * @throws PdfParsingException if the file is null, empty, invalid, encrypted,
     *                             image-only, or otherwise unreadable
     */
    public String extractText(MultipartFile file) {
        validateFile(file);

        log.debug("Extracting text from PDF: name='{}', size={}KB",
                file.getOriginalFilename(), file.getSize() / 1024);

        // PDFBox 3.x: use Loader.loadPDF() + RandomAccessReadBuffer instead of
        // the removed PDDocument.load(InputStream) from 2.x
        try (InputStream inputStream = file.getInputStream();
             PDDocument document = Loader.loadPDF(new RandomAccessReadBuffer(inputStream))) {

            if (document.isEncrypted()) {
                throw new PdfParsingException(
                        "The uploaded PDF '" + file.getOriginalFilename() +
                        "' is password-protected. Please upload an unencrypted PDF.");
            }

            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true); // better ordering for multi-column layouts

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
            throw e; // re-throw domain exceptions as-is
        } catch (IOException e) {
            throw new PdfParsingException(
                    "IO error reading PDF '" + file.getOriginalFilename() + "': " + e.getMessage(), e);
        } catch (Exception e) {
            throw new PdfParsingException(
                    "Unexpected error parsing PDF '" + file.getOriginalFilename() + "': " + e.getMessage(), e);
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new PdfParsingException("Uploaded file is null or empty.");
        }
        String contentType = file.getContentType();
        if (contentType == null || !contentType.equalsIgnoreCase(PDF_MIME_TYPE)) {
            throw new PdfParsingException(
                    "Invalid file type: expected 'application/pdf', got '" + contentType + "'. " +
                    "Please upload a PDF file.");
        }
    }

    /**
     * Lightly cleans PDFBox-extracted text:
     * <ol>
     *   <li>Normalizes Windows line endings ({@code \r\n}) to Unix ({@code \n})</li>
     *   <li>Collapses 3+ consecutive blank lines into 2</li>
     *   <li>Trims leading/trailing whitespace</li>
     * </ol>
     */
    private String cleanText(String rawText) {
        return rawText
                .replace("\r\n", "\n")
                .replaceAll("\n{3,}", "\n\n")
                .strip();
    }
}
