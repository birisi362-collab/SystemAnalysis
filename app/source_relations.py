"""Distinguish documentary support from graph context without rewriting imports."""
def source_relations(architecture, requirement_id):
    objects = architecture.components + architecture.connections
    evidence_ids = {o.id for o in objects if any(e.requirement_id == requirement_id for e in o.evidence)}
    endpoints = {x for e in architecture.connections if e.id in evidence_ids for x in (e.source, e.target)}
    cov = next((c for c in architecture.requirement_coverage if c.requirement_id == requirement_id), None)
    explicit = set(cov.contextual_component_ids + cov.contextual_connection_ids) if cov else set()
    selected = set(cov.related_component_ids + cov.related_connection_ids) if cov else set()
    # Legacy endpoint links are inferred only from a connection citing THIS source.
    inferred = (selected & endpoints) - evidence_ids
    contextual = explicit | inferred | (endpoints - evidence_ids)
    direct = selected - explicit - inferred
    return dict(evidence_ids=sorted(evidence_ids), direct_ids=sorted(direct),
                contextual_ids=sorted(contextual), inferred_ids=sorted(inferred),
                explicit_context_ids=sorted(explicit), unsupported_ids=sorted(direct-evidence_ids))
