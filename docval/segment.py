"""Split a multi-page upload into sub-documents by classified page type.

A single PDF may bundle several distinct documents (e.g. ID + lease +
certificate scanned together). Each page is classified independently (Stufe 1);
consecutive pages sharing a type form one sub-document, and the boundary is cut
wherever the type changes. A single-page upload, or a multi-page document whose
pages all classify the same, yields exactly one segment — no false splits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .config import Config
from .model_client import ModelClient
from .schemas import Classification


@dataclass
class Segment:
    """One detected sub-document: its Stufe-1 classification and its pages."""

    classification: Classification
    images: list[bytes] = field(default_factory=list)


def segment_pages(
    images: Sequence[bytes], model: ModelClient, config: Config
) -> list[Segment]:
    """Group pages into sub-documents, cutting where the document type changes."""
    segments: list[Segment] = []
    for page in images:
        classification = model.classify([page], config)
        if segments and segments[-1].classification.document_type == classification.document_type:
            segments[-1].images.append(page)
        else:
            segments.append(Segment(classification=classification, images=[page]))
    return segments
