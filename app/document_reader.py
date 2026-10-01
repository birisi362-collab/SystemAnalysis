"""Read ordered source blocks without discarding their locations."""
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SourceBlock:
    text: str
    location: str
    kind: str = 'paragraph'
    section: str | None = None


def read_blocks(path_str: str) -> list[SourceBlock]:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == '.txt':
        # Fail explicitly rather than silently replacing corrupted text.
        return [SourceBlock(t, f'line:{i}', 'line') for i, t in
                enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1)]
    if suffix == '.docx':
        from docx import Document
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        doc = Document(str(path)); blocks = []; p = t = 0; section = None
        for child in doc.element.body.iterchildren():
            if child.tag == qn('w:p'):
                p += 1; paragraph = Paragraph(child, doc)
                heading = bool(paragraph.style and paragraph.style.name.startswith('Heading'))
                if heading:
                    section = paragraph.text.strip()
                blocks.append(SourceBlock(paragraph.text, f'paragraph:{p}',
                                          'heading' if heading else 'paragraph', section))
            elif child.tag == qn('w:tbl'):
                t += 1
                for r, row in enumerate(Table(child, doc).rows, 1):
                    blocks.append(SourceBlock(' | '.join(c.text.replace('\n', ' ') for c in row.cells),
                                              f'table:{t}/row:{r}', 'table', section))
        return blocks
    if suffix == '.pdf':
        from pypdf import PdfReader
        blocks = []
        for p, page in enumerate(PdfReader(str(path)).pages, 1):
            text = page.extract_text() or ''
            if not text.strip():
                raise ValueError(f'PDF page {p} has no extractable text. OCR is required; analysis stopped to avoid silent omission.')
            blocks.extend(SourceBlock(t, f'page:{p}/line:{i}', 'line')
                          for i, t in enumerate(text.splitlines(), 1))
        return blocks
    raise ValueError(f'Unsupported document type: {suffix}')


def read_document(path_str: str) -> str:
    return '\n'.join(b.text for b in read_blocks(path_str))


def read_txt(path: Path) -> str:
    return read_document(str(path))


def read_docx(path: Path) -> str:
    return read_document(str(path))


def read_pdf(path: Path) -> str:
    return read_document(str(path))
