"""Document parser service for extracting and cleaning raw text from CV and JD documents."""
import io
import logging
import os
import re
import unicodedata
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from matching_cv.app.schemas.document import DocumentExtractResponse

logger = logging.getLogger(__name__)

# Regex pattern to match control characters except tab (\x09) and newline (\x0a)
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class DocumentParserService:
    """Service responsible for parsing, extracting, and cleaning text from documents."""

    @staticmethod
    def clean_extracted_text(raw_text: str) -> str:
        """
        Clean and normalize raw extracted text:
        - Normalize unicode to standard NFC form.
        - Strip invalid control characters and null bytes.
        - Normalize carriage returns (\r\n -> \n, \r -> \n).
        - Remove trailing/leading whitespaces on each line.
        - Collapse 3 or more consecutive newlines into at most 2 newlines (\n\n).
        - Collapse multiple horizontal spaces or tabs into a single space.
        """
        if not raw_text:
            return ""

        # 1. Unicode NFC normalization
        text = unicodedata.normalize("NFC", raw_text)

        # 2. Strip null bytes and non-printable control characters
        text = CONTROL_CHAR_REGEX.sub("", text)

        # 3. Standardize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 4. Clean up spaces on individual lines while keeping linebreaks
        cleaned_lines = []
        for line in text.split("\n"):
            # Replace multiple consecutive horizontal whitespace characters with a single space
            normalized_line = re.sub(r"[ \t]+", " ", line).strip()
            cleaned_lines.append(normalized_line)

        reconstructed_text = "\n".join(cleaned_lines)

        # 5. Collapse 3+ consecutive line breaks into at most 2 (\n\n) to preserve paragraph structure
        reconstructed_text = re.sub(r"\n{3,}", "\n\n", reconstructed_text)

        return reconstructed_text.strip()

    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, int]:
        """
        Extract raw text and total page count from PDF binary data.
        """
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
            if total_pages == 0:
                return "", 0

            extracted_pages = []
            for page_idx, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        extracted_pages.append(page_text.strip())
                except Exception as page_err:
                    logger.warning(
                        f"Failed to extract text from PDF page {page_idx + 1}: {page_err}"
                    )

            full_text = "\n\n".join(extracted_pages)
            return full_text, total_pages

        except PdfReadError as pdf_err:
            logger.error(f"Corrupted or password-protected PDF: {pdf_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tệp PDF không hợp lệ, bị mã hóa hoặc bị hỏng: {str(pdf_err)}",
            ) from pdf_err
        except Exception as e:
            logger.error(f"Unexpected error while parsing PDF: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi hệ thống khi trích xuất dữ liệu từ tệp PDF: {str(e)}",
            ) from e

    @staticmethod
    def extract_text_from_txt(file_bytes: bytes) -> str:
        """
        Decode raw bytes from TXT file with multiple encoding fallbacks.
        Order: utf-8 -> utf-16 -> latin-1 (iso-8859-1).
        """
        encodings = ["utf-8", "utf-16", "latin-1"]
        for enc in encodings:
            try:
                return file_bytes.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue

        # Last resort fallback with replacement characters
        return file_bytes.decode("utf-8", errors="replace")

    async def parse_file(self, file: UploadFile) -> DocumentExtractResponse:
        """
        Validate file format, extract raw text, clean text, and compile document metadata.
        """
        filename = file.filename or "unknown_document"
        _, ext = os.path.splitext(filename.lower())

        # Validate file extension
        if ext not in [".pdf", ".txt"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Định dạng tệp '{ext}' không được hỗ trợ. "
                    "Hệ thống chỉ hỗ trợ tệp định dạng .pdf và .txt."
                ),
            )

        # Read binary content
        try:
            content = await file.read()
        except Exception as read_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể đọc nội dung tệp tải lên: {str(read_err)}",
            ) from read_err

        if not content or len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tệp tin rỗng hoặc không có dữ liệu nội dung.",
            )

        # Extraction branch
        raw_extracted_text = ""
        total_pages: Optional[int] = None
        file_type = "pdf" if ext == ".pdf" else "txt"

        if ext == ".pdf":
            raw_extracted_text, total_pages = self.extract_text_from_pdf(content)
        else:
            raw_extracted_text = self.extract_text_from_txt(content)

        # Clean extracted text
        cleaned_text = self.clean_extracted_text(raw_extracted_text)

        character_count = len(cleaned_text)
        word_count = len(cleaned_text.split()) if cleaned_text else 0

        logger.info(
            f"Successfully parsed '{filename}' ({file_type}): "
            f"pages={total_pages}, chars={character_count}, words={word_count}"
        )

        return DocumentExtractResponse(
            filename=filename,
            file_type=file_type,
            total_pages=total_pages,
            character_count=character_count,
            word_count=word_count,
            raw_text=cleaned_text,
        )


# Global service instance
document_parser_service = DocumentParserService()
