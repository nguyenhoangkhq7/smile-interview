"""Pydantic schemas for document parsing and text cleaning."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class RawTextPayload(BaseModel):
    """Payload for direct raw text cleaning and normalization."""

    text: str = Field(
        ...,
        min_length=1,
        description="Chuỗi văn bản thô cần được làm sạch và chuẩn hóa",
        examples=[
            "Kỹ sư  AI / Machine Learning \r\n\r\n\r\n Thành thạo Python, PyTorch, FastAPI. \x00 Có kinh nghiệm triển khai LLM."
        ],
    )


class CleanTextResponse(BaseModel):
    """Response payload for cleaned text."""

    cleaned_text: str = Field(
        ...,
        description="Văn bản đã qua quy trình làm sạch và chuẩn hóa khoảng cách",
    )
    character_count: int = Field(
        ...,
        ge=0,
        description="Tổng số ký tự sau khi làm sạch",
        examples=[1024],
    )
    word_count: int = Field(
        ...,
        ge=0,
        description="Tổng số từ trong văn bản đã làm sạch",
        examples=[168],
    )


class DocumentExtractResponse(BaseModel):
    """Response payload for document text extraction (CV / JD files)."""

    filename: str = Field(
        ...,
        description="Tên file gốc được tải lên",
        examples=["cv_nguyen_van_a.pdf"],
    )
    file_type: Literal["pdf", "txt"] = Field(
        ...,
        description="Định dạng tệp đã xử lý (pdf hoặc txt)",
        examples=["pdf"],
    )
    total_pages: Optional[int] = Field(
        default=None,
        description="Tổng số trang văn bản (đối với PDF) hoặc None (đối với TXT)",
        examples=[2],
    )
    character_count: int = Field(
        ...,
        ge=0,
        description="Tổng số ký tự văn bản sau khi làm sạch",
        examples=[3250],
    )
    word_count: int = Field(
        ...,
        ge=0,
        description="Tổng số từ văn bản sau khi làm sạch",
        examples=[512],
    )
    raw_text: str = Field(
        ...,
        description="Chuỗi văn bản hoàn chỉnh đã qua làm sạch và bảo toàn cấu trúc dòng",
    )


class CVJDExtractResponse(BaseModel):
    """Response payload containing extracted text from both CV and JD without similarity computation."""

    cv: DocumentExtractResponse = Field(
        ...,
        description="Thông tin và toàn bộ nội dung văn bản trích xuất từ tệp CV ứng viên",
    )
    jd: DocumentExtractResponse = Field(
        ...,
        description="Thông tin và toàn bộ nội dung văn bản trích xuất từ tệp JD mô tả công việc",
    )
