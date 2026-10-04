from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    quote: Optional[str] = None


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: Optional[str] = None
    category: Literal["system", "subsystem", "component", "external"] = "component"
    evidence: List[EvidenceRef] = Field(default_factory=list)


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: str
    target: str
    direction: Literal['unidirectional', 'bidirectional'] = 'unidirectional'
    type: Literal[
        "data", "control", "power", "communication", "mechanical", "thermal", "unknown"
    ] = "unknown"
    protocol: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    evidence: List[EvidenceRef] = Field(default_factory=list)


class RequirementCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    status: Literal["covered", "partially_covered", "unmapped", "not_architectural"]
    related_component_ids: List[str] = Field(default_factory=list)
    related_connection_ids: List[str] = Field(default_factory=list)
    contextual_component_ids: List[str] = Field(default_factory=list)
    contextual_connection_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["add", "update", "remove"]
    kind: Literal["component", "connection"]
    id: str = Field(min_length=1)
    value: dict = Field(default_factory=dict)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    severity: Literal["info", "low", "medium", "high", "critical"]
    type: Literal[
        "contradiction",
        "missing_interface",
        "missing_connection",
        "ambiguous",
        "traceability",
        "classification",
        "other",
    ]
    title: str
    description: str
    evidence: List[EvidenceRef] = Field(default_factory=list)
    related_component_ids: List[str] = Field(default_factory=list)
    related_connection_ids: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    proposed_changes: List[ProposedChange] = Field(default_factory=list)
    open_details: List[str] = Field(default_factory=list)


class ArchitectureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_name: str = Field(min_length=1)
    purpose: Optional[str] = None
    components: List[Component]
    connections: List[Connection]
    requirement_coverage: List[RequirementCoverage] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: List[Finding] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    related_id: Optional[str] = None
    source_id: Optional[str] = None
    object_id: Optional[str] = None
    finding_id: Optional[str] = None


class FinalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "7.0"
    source_catalog: List[dict] = Field(default_factory=list)
    run_metadata: dict = Field(default_factory=dict)
    review_status: Literal["completed", "partial", "skipped", "failed"] = "completed"
    architecture: ArchitectureModel
    analysis: AnalysisResult
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
