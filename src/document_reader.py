"""Read selectable text from supplier proposal PDFs."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader


class PDFExtractionError(ValueError):
	"""Raised when a PDF cannot provide usable proposal text."""


def extract_pdf_text(source: str | Path | BinaryIO) -> str:
	"""Extract text from a PDF path or a seekable uploaded binary file.

	Page text is returned in document order, separated by blank lines. A PDF
	with no pages or no extractable text raises ``PDFExtractionError`` rather
	than returning an empty proposal.
	"""
	if isinstance(source, (str, Path)):
		path = Path(source)
		try:
			with path.open("rb") as pdf_file:
				return _extract_from_stream(pdf_file, str(path))
		except PDFExtractionError:
			raise
		except (OSError, TypeError, ValueError) as error:
			raise PDFExtractionError(
				f"Could not open PDF '{path}': {error}. Check that the path exists "
				"and the file is readable."
			) from error

	filename = str(getattr(source, "name", "uploaded PDF"))
	if not callable(getattr(source, "read", None)) or not callable(
		getattr(source, "seek", None)
	):
		raise PDFExtractionError(
			"PDF input must be a file path or a seekable binary uploaded file."
		)
	return _extract_from_stream(source, filename)


def _extract_from_stream(pdf_file: BinaryIO, filename: str) -> str:
	original_position: int | None
	try:
		original_position = pdf_file.tell()
	except (AttributeError, OSError):
		original_position = None

	try:
		pdf_file.seek(0)
	except (AttributeError, OSError) as error:
		raise PDFExtractionError(
			f"Cannot read '{filename}' because its file stream is not seekable. "
			"Upload the PDF again as a standard file."
		) from error

	try:
		reader = PdfReader(pdf_file, strict=True)
		if reader.is_encrypted:
			raise PDFExtractionError(
				f"'{filename}' is password-protected. Upload an unlocked PDF."
			)

		pages = reader.pages
		if len(pages) == 0:
			raise PDFExtractionError(
				f"'{filename}' contains no pages. Upload a non-empty PDF proposal."
			)

		page_texts: list[str] = []
		for page_number, page in enumerate(pages, start=1):
			try:
				page_texts.append((page.extract_text() or "").strip())
			except Exception as error:
				raise PDFExtractionError(
					f"Could not extract text from page {page_number} of '{filename}'. "
					"Check that the PDF is valid or re-export it."
				) from error

		extracted_text = "\n\n".join(text for text in page_texts if text)
		if not extracted_text:
			raise PDFExtractionError(
				f"No selectable text was found in '{filename}'. It may be scanned or "
				"image-only; run OCR on the PDF and upload the searchable result."
			)
		return extracted_text
	except PDFExtractionError:
		raise
	except Exception as error:
		raise PDFExtractionError(
			f"Could not read '{filename}': the PDF may be malformed or unsupported. "
			"Check the file or export a fresh PDF and try again."
		) from error
	finally:
		if original_position is not None:
			try:
				pdf_file.seek(original_position)
			except (AttributeError, OSError):
				pass
