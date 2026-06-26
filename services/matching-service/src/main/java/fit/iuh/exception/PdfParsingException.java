package fit.iuh.exception;

/**
 * Thrown when Apache PDFBox fails to extract text from an uploaded PDF file.
 * Causes: corrupted file, password-protected PDF, non-PDF MIME type, empty file.
 */
public class PdfParsingException extends RuntimeException {

    public PdfParsingException(String message) {
        super(message);
    }

    public PdfParsingException(String message, Throwable cause) {
        super(message, cause);
    }
}
