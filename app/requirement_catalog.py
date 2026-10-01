import hashlib
import re
from dataclasses import dataclass, field
from .document_reader import SourceBlock

@dataclass
class RequirementEntry:
    requirement_id: str
    text: str
    section: str | None = None
    locations: list[str] = field(default_factory=list)
    original_id: str | None = None

    def formatted(self) -> str:
        return f'[{self.requirement_id}] [{", ".join(self.locations)}] {self.text}'

EXPLICIT = re.compile(r'^(?P<id>(?:REQ|SYS|IF|G|R)[-_]\d+(?:[.\-_]\d+)*|\d+(?:\.\d+)+)[\s:|)]+(?P<text>.+)$', re.I)
NUMBERED = re.compile(r'^\d+\.\s+(.+)$')
OBLIGATION = re.compile(r'\b(shall|must|will)\b|(?:malıdır|melidir|acaktır|ecektir|zorundadır)', re.I)


def build_catalog(document_text: str) -> list[RequirementEntry]:
    return build_catalog_blocks([SourceBlock(t, f'line:{i}', 'line')
                                 for i, t in enumerate(document_text.splitlines(), 1)])


def build_catalog_blocks(blocks: list[SourceBlock]) -> list[RequirementEntry]:
    entries = []; pending = []; locations = []; pending_id = None
    section = None; seen = {}

    def flush():
        nonlocal pending, locations, pending_id
        if not pending:
            return
        text = ' '.join(pending)
        original = pending_id
        rid = original or 'R-' + hashlib.sha256(text.encode()).hexdigest()[:12]
        seen[rid] = seen.get(rid, 0) + 1
        unique = rid if seen[rid] == 1 else f'{rid}~{seen[rid]}'
        entries.append(RequirementEntry(unique, text, section, locations[:], original))
        pending = []; locations = []; pending_id = None

    for b in blocks:
        line = ' '.join(b.text.strip().split())
        if not line:
            flush(); continue
        explicit = EXPLICIT.match(line)
        numbered = NUMBERED.match(line)
        heading = b.kind == 'heading' or (numbered and len(line) < 140 and not OBLIGATION.search(line))
        if heading:
            flush(); section = line; continue
        if b.section and b.section != section:
            flush(); section = b.section
        if explicit:
            flush()
            rid = explicit.group('id')
            pending_id = 'REQ-' + rid if rid[0].isdigit() else rid.upper()
            pending = [line]; locations = [b.location]
        elif pending and pending_id and b.kind != 'table':
            # Wrapped lines/paragraphs belong to the explicit requirement until a
            # blank, heading, next explicit ID, or table boundary. Review catalog for ambiguous files.
            pending.append(line); locations.append(b.location)
        else:
            flush(); pending = [line]; locations = [b.location]
        if b.kind == 'table':
            flush()
    flush()
    return entries


def catalog_as_prompt(entries):
    return '\n'.join(e.formatted() for e in entries)
