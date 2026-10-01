"""Deterministic integrity checks, not a semantic truth oracle."""
import re
import unicodedata
from collections import Counter
from .models import ArchitectureModel, AnalysisResult, ValidationIssue
from .source_relations import source_relations

PATTERNS = {
    'RS-422': r'\bRS[ -]?422\b', 'RS-485': r'\bRS[ -]?485\b',
    'LVDS': r'\bLVDS\b', 'PCIe': r'\bPCI[ -]?E\b', 'I2C': r'\bI[²2]C\b',
    'Ethernet': r'\b(?:Gigabit\s+)?Ethernet\b', 'TCP': r'\bTCP(?:/IP)?\b',
    'UDP': r'\bUDP\b', 'SPI': r'\bSPI\b', 'CAN': r'\bCAN(?:[ -]?FD)?\b',
    'USB': r'\bUSB\b',
}

def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text or '').split())


def protocols(text):
    # CAN is intentionally case-sensitive: English "can" is not a bus name.
    return {k for k, p in PATTERNS.items() if re.search(p, text or '', 0 if k == 'CAN' else re.I)}


def validate_architecture(architecture: ArchitectureModel, entries, analysis: AnalysisResult | None = None):
    issues = []; sources = {e.requirement_id: e for e in entries}
    cs = {c.id for c in architecture.components}; es = {c.id for c in architecture.connections}
    def add(code, message, rid=None, severity='error', source_id=None, object_id=None, finding_id=None):
        issues.append(ValidationIssue(code=code, message=message, related_id=rid, severity=severity,
            source_id=source_id, object_id=object_id, finding_id=finding_id))
    def duplicates(ids, code):
        for rid, n in Counter(ids).items():
            if n > 1: add(code, f'{rid}: {n} occurrences.', rid)
    def refs(obj):
        owner = dict(source_id=getattr(obj, 'requirement_id', None), finding_id=getattr(obj, 'id', None))
        for rid in set(obj.related_component_ids + getattr(obj, 'contextual_component_ids', [])):
            if rid not in cs: add('UNKNOWN_COMPONENT_REF', f'{rid}: referenced component does not exist.', rid, **owner)
        for rid in set(obj.related_connection_ids + getattr(obj, 'contextual_connection_ids', [])):
            if rid not in es: add('UNKNOWN_CONNECTION_REF', f'{rid}: referenced connection does not exist.', rid, **owner)
    def evidence(obj):
        valid = []
        if not obj.evidence: add('MISSING_EVIDENCE', 'No supporting source was provided.', obj.id)
        for ev in obj.evidence:
            source = sources.get(ev.requirement_id)
            if source is None:
                add('UNKNOWN_EVIDENCE_REF', f'Unknown requirement: {ev.requirement_id}', obj.id)
            elif not normalize(ev.quote):
                add('MISSING_QUOTE', f'No verbatim quote for {ev.requirement_id}.', obj.id)
            elif normalize(ev.quote) not in normalize(source.text):
                add('QUOTE_NOT_IN_SOURCE', f'Quote is not present in {ev.requirement_id}.', obj.id)
            else:
                valid.append(ev)
        return valid
    duplicates([e.requirement_id for e in entries], 'DUPLICATE_SOURCE_ID')
    duplicates([e.original_id for e in entries if e.original_id], 'DUPLICATE_SOURCE_ID')
    duplicates([c.id for c in architecture.components], 'DUPLICATE_COMPONENT_ID')
    duplicates([c.id for c in architecture.connections], 'DUPLICATE_CONNECTION_ID')
    duplicates([c.requirement_id for c in architecture.requirement_coverage], 'DUPLICATE_COVERAGE')
    if not architecture.components:
        add('EMPTY_ARCHITECTURE', 'No components extracted; a human must confirm that the source is non-architectural.', severity='warning')
    for component in architecture.components:
        evidence(component)
    for conn in architecture.connections:
        if conn.source not in cs: add('UNKNOWN_SOURCE', 'Connection source does not exist.', conn.id)
        if conn.target not in cs: add('UNKNOWN_TARGET', 'Connection target does not exist.', conn.id)
        valid = evidence(conn)
        quote_protocols = set().union(*(protocols(ev.quote) for ev in valid)) if valid else set()
        declared = protocols(conn.protocol)
        if quote_protocols and not conn.protocol:
            add('EXPLICIT_PROTOCOL_NOT_CAPTURED', f'Quote names {sorted(quote_protocols)}, protocol is empty.', conn.id)
        elif quote_protocols and not (quote_protocols & declared):
            add('PROTOCOL_MISMATCH', 'Declared protocol does not match any known protocol in the verified quote.', conn.id, 'warning')
        elif quote_protocols - declared:
            add('PROTOCOL_REVIEW_REQUIRED', 'Quote contains additional technologies; check whether they apply to this connection.', conn.id, 'warning')
        if valid and declared - quote_protocols and not (quote_protocols and not (quote_protocols & declared)):
            add('PROTOCOL_NOT_SUPPORTED', 'Declared technology is absent from verified quotes.', conn.id, 'warning')
        source_protocols = set().union(*(protocols(sources[ev.requirement_id].text) for ev in valid)) if valid else set()
        if source_protocols and not quote_protocols:
            add('PROTOCOL_SOURCE_REVIEW', 'Source names a technology omitted from the selected quote; check its applicability.', conn.id, 'warning')
        if conn.protocol and valid and not declared:
            # Unknown protocol values are not assumed wrong, but require review.
            if not any(normalize(conn.protocol).casefold() in normalize(sources[e.requirement_id].text).casefold() for e in valid):
                add('PROTOCOL_UNVERIFIED', 'Protocol value could not be matched to its sources.', conn.id, 'warning')
    coverage = {c.requirement_id: c for c in architecture.requirement_coverage}
    for item in architecture.requirement_coverage:
        refs(item)
        if item.requirement_id not in sources: add('UNKNOWN_COVERAGE_REQUIREMENT', 'Coverage cites unknown source.', item.requirement_id)
        if item.status in ('covered', 'partially_covered'):
            if not item.related_component_ids and not item.related_connection_ids and not item.contextual_component_ids and not item.contextual_connection_ids:
                add('COVERAGE_WITHOUT_LINKS', 'Covered source has no related objects.', item.requirement_id)
            relations = source_relations(architecture, item.requirement_id)
            objects = [x for x in architecture.components + architecture.connections if x.id in relations['direct_ids']]
            for obj in objects:
                if not any(e.requirement_id == item.requirement_id for e in obj.evidence):
                    add('COVERAGE_EVIDENCE_MISMATCH', 'Direct coverage link is not backed by the object evidence.', item.requirement_id, 'warning', source_id=item.requirement_id, object_id=obj.id)
            if not objects and relations['explicit_context_ids'] and not relations['evidence_ids']:
                add('COVERAGE_CONTEXT_ONLY', 'Covered source has context links but no direct documentary support.', item.requirement_id, 'warning', source_id=item.requirement_id)
    for rid in sources:
        if rid not in coverage: add('MISSING_COVERAGE', 'No coverage classification.', rid, 'warning')
        elif coverage[rid].status == 'unmapped': add('UNMAPPED_REQUIREMENT', 'Source is explicitly unmapped.', rid, 'warning')
        elif coverage[rid].status == 'partially_covered': add('PARTIAL_COVERAGE', 'Source is only partially covered.', rid, 'warning')
    connected = {endpoint for c in architecture.connections for endpoint in (c.source, c.target)}
    for c in architecture.components:
        if c.category != 'system' and c.id not in connected: add('ORPHAN_COMPONENT', 'No extracted connection.', c.id, 'warning')
    if analysis is not None:
        duplicates([f.id for f in analysis.findings], 'DUPLICATE_FINDING_ID')
        for finding in analysis.findings:
            evidence(finding); refs(finding)
    return issues
