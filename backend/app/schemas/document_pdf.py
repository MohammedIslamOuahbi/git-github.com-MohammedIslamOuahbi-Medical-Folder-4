from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List


class DocumentPdfItem(BaseModel):
    id: int
    date: Optional[str] = None
    doctor: Optional[str] = None
    status: str
    pdf_exists: bool


class DocumentPdfListResponse(BaseModel):
    items: List[DocumentPdfItem]
