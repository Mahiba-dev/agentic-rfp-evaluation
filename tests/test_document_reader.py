"""Synthetic PDF tests for document text extraction."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from src.document_reader import PDFExtractionError, extract_pdf_text


def make_synthetic_pdf(page_contents: list[bytes]) -> bytes:
    """Build a tiny PDF with optional text drawing commands for each page."""
    objects: list[bytes] = [b""]
    page_references: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for content in page_contents:
        page_number = len(objects)
        content_number = page_number + 1
        page_references.append(f"{page_number} 0 R".encode("ascii"))
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> "
                f"/Contents {content_number} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"\nendstream"
        )

    objects[2] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(page_references)
        + f"] /Count {len(page_references)} >>".encode("ascii")
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects[1:], start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


class DocumentReaderTests(unittest.TestCase):
    def test_extracts_text_page_by_page_from_a_path(self) -> None:
        pdf_bytes = make_synthetic_pdf(
            [
                b"BT /F1 12 Tf 40 740 Td (First page proposal) Tj ET",
                b"BT /F1 12 Tf 40 740 Td (Second page pricing) Tj ET",
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "proposal.pdf"
            pdf_path.write_bytes(pdf_bytes)

            text = extract_pdf_text(pdf_path)

        self.assertEqual(text, "First page proposal\n\nSecond page pricing")

    def test_accepts_uploaded_file_object_and_restores_its_position(self) -> None:
        pdf_file = io.BytesIO(
            make_synthetic_pdf([b"BT /F1 12 Tf 40 740 Td (Uploaded proposal) Tj ET"])
        )
        pdf_file.name = "uploaded.pdf"
        pdf_file.seek(7)

        self.assertEqual(extract_pdf_text(pdf_file), "Uploaded proposal")
        self.assertEqual(pdf_file.tell(), 7)

    def test_rejects_a_zero_page_pdf(self) -> None:
        with self.assertRaisesRegex(PDFExtractionError, "contains no pages"):
            extract_pdf_text(io.BytesIO(make_synthetic_pdf([])))

    def test_rejects_scanned_or_image_only_pdf_with_ocr_guidance(self) -> None:
        image_only_content = b"q 0 0 0 rg 10 10 20 20 re f Q"
        with self.assertRaisesRegex(PDFExtractionError, "run OCR"):
            extract_pdf_text(io.BytesIO(make_synthetic_pdf([image_only_content])))

    def test_rejects_malformed_pdf_with_recovery_guidance(self) -> None:
        with self.assertRaisesRegex(PDFExtractionError, "malformed or unsupported"):
            extract_pdf_text(io.BytesIO(b"this is not a PDF"))

    def test_reports_missing_file_path_actionably(self) -> None:
        with self.assertRaisesRegex(PDFExtractionError, "Check that the path exists"):
            extract_pdf_text(Path("missing-proposal.pdf"))


if __name__ == "__main__":
    unittest.main()