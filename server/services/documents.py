"""Document management helpers including OCR and cloud sync metadata."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List, Optional

from PIL import Image
from sqlalchemy.orm import Session

try:  # optional dependency for OCR
    import pytesseract
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None

from ..config import settings
from ..models import Dokument


class DocumentService:
    """Persist documents, extract OCR text and build search indices."""

    def __init__(self, session: Session, storage_dir: Optional[Path] = None) -> None:
        self.session = session
        self.storage_dir = storage_dir or Path("storage/documents")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_document(
        self,
        *,
        titel: str,
        filename: str,
        content_type: Optional[str],
        payload: bytes,
        produkt_id: Optional[int],
        fahrzeug_id: Optional[int],
        tags: Iterable[str],
    ) -> Dokument:
        storage_name = hashlib.sha1(payload).hexdigest()
        extension = Path(filename).suffix
        target_path = self.storage_dir / f"{storage_name}{extension}"
        target_path.write_bytes(payload)

        ocr_text = self._extract_text(target_path)
        checksum = hashlib.sha256(payload).hexdigest()
        cloud_url = self._build_cloud_url(target_path.name)

        dokument = Dokument(
            titel=titel,
            original_name=filename,
            content_type=content_type,
            dateipfad=str(target_path),
            cloud_url=cloud_url,
            ocr_text=ocr_text,
            tags=",".join(sorted({tag.strip().lower() for tag in tags if tag})),
            produkt_id=produkt_id,
            fahrzeug_id=fahrzeug_id,
            checksum=checksum,
        )
        self.session.add(dokument)
        self.session.flush()
        return dokument

    def search(self, query: Optional[str] = None, tags: Optional[List[str]] = None) -> List[Dokument]:
        queryset = self.session.query(Dokument)
        if query:
            like_term = f"%{query.lower()}%"
            queryset = queryset.filter(Dokument.ocr_text.ilike(like_term) | Dokument.titel.ilike(like_term))
        if tags:
            normalized = [tag.strip().lower() for tag in tags if tag]
            for tag in normalized:
                queryset = queryset.filter(Dokument.tags.ilike(f"%{tag}%"))
        return queryset.order_by(Dokument.created_at.desc()).all()

    def _extract_text(self, path: Path) -> str:
        if not pytesseract:
            return ""
        try:
            image = Image.open(path)
        except Exception:  # pragma: no cover - fallback for unsupported formats
            return ""
        text = pytesseract.image_to_string(image, lang=settings.ocr_languages)
        return text.strip()

    def _build_cloud_url(self, filename: str) -> Optional[str]:
        if not settings.cloud_storage_base_url:
            return None
        return f"{settings.cloud_storage_base_url.rstrip('/')}/{filename}"
