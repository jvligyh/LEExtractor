"""PRISMA 2020 flow diagram tracking for systematic literature reviews.

Tracks papers through the standard PRISMA phases:
1. Identification — papers found via database search + other methods
2. Screening — after deduplication, title/abstract screening
3. Eligibility — full-text assessment
4. Included — final set for synthesis
"""

from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from litsearch.models import Paper


class ScreeningDecision(Enum):
    PENDING = "pending"
    ACCEPT = "accept"
    REJECT = "reject"
    MAYBE = "maybe"


@dataclass
class PRISMARecord:
    """Tracks a single paper through the PRISMA pipeline."""

    paper: Paper
    source: str = ""           # "database_search" | "snowballing" | "similar" | "manual"
    screening_decision: ScreeningDecision = ScreeningDecision.PENDING
    rejection_reason: str = ""
    relevance_score: float = 0.0


@dataclass
class PRISMAReport:
    """Complete PRISMA 2020 flow data."""

    # Identification
    database_results: int = 0
    snowball_results: int = 0
    similar_results: int = 0
    manual_additions: int = 0

    # After deduplication
    records_after_dedup: int = 0

    # Screening
    records_screened: int = 0
    records_excluded_title_abstract: int = 0

    # Eligibility
    full_text_assessed: int = 0
    full_text_excluded: int = 0
    full_text_exclusion_reasons: dict[str, int] = field(default_factory=dict)

    # Included
    studies_included: int = 0

    # All records with decisions
    records: list[PRISMARecord] = field(default_factory=list)

    def to_flow_dict(self) -> dict:
        """Export as dict suitable for rendering a PRISMA flow diagram."""
        return {
            "identification": {
                "database_search": self.database_results,
                "snowballing": self.snowball_results,
                "similar_papers": self.similar_results,
                "manual_additions": self.manual_additions,
                "total": (
                    self.database_results + self.snowball_results
                    + self.similar_results + self.manual_additions
                ),
            },
            "screening": {
                "after_dedup": self.records_after_dedup,
                "screened": self.records_screened,
                "excluded_title_abstract": self.records_excluded_title_abstract,
            },
            "eligibility": {
                "full_text_assessed": self.full_text_assessed,
                "full_text_excluded": self.full_text_excluded,
                "reasons": self.full_text_exclusion_reasons,
            },
            "included": {
                "studies": self.studies_included,
            },
        }

    def to_mermaid(self) -> str:
        """Generate a Mermaid PRISMA flow diagram."""
        d = self.to_flow_dict()
        ident = d["identification"]
        screen = d["screening"]
        elig = d["eligibility"]
        incl = d["included"]

        return f"""```mermaid
flowchart TD
    A["Records identified<br/>Database: {ident['database_search']}<br/>Snowballing: {ident['snowballing']}<br/>Similar: {ident['similar_papers']}<br/>Manual: {ident['manual_additions']}<br/><b>Total: {ident['total']}</b>"]
    B["Records after duplicates removed<br/><b>n = {screen['after_dedup']}</b>"]
    C["Records screened<br/>(title/abstract)<br/><b>n = {screen['screened']}</b>"]
    D["Records excluded<br/><b>n = {screen['excluded_title_abstract']}</b>"]
    E["Full-text assessed<br/><b>n = {elig['full_text_assessed']}</b>"]
    F["Full-text excluded<br/><b>n = {elig['full_text_excluded']}</b>"]
    G["Studies included<br/><b>n = {incl['studies']}</b>"]

    A --> B
    B --> C
    C --> D
    C --> E
    E --> F
    E --> G
```"""


class PRISMATracker:
    """Manages the PRISMA pipeline for a literature review session."""

    def __init__(self):
        self.records: dict[str, PRISMARecord] = {}  # paper ID -> record
        self._id_counter: dict[str, int] = defaultdict(int)

    def add_papers(
        self, papers: list[Paper], source: str = "database_search"
    ) -> int:
        """Add papers to the identification phase. Returns count of new papers."""
        added = 0
        for p in papers:
            key = (p.doi or p.id).lower()
            if key not in self.records:
                self.records[key] = PRISMARecord(paper=p, source=source)
                added += 1
        return added

    def get_screening_queue(self) -> list[PRISMARecord]:
        """Get papers pending screening, sorted by relevance."""
        pending = [
            r for r in self.records.values()
            if r.screening_decision == ScreeningDecision.PENDING
        ]
        pending.sort(key=lambda r: r.relevance_score, reverse=True)
        return pending

    def _find_key(self, paper_id: str) -> str | None:
        """Resolve a paper_id to the internal records key."""
        key = paper_id.lower()
        if key in self.records:
            return key
        # Also try matching against paper.id and paper.doi
        for k, rec in self.records.items():
            if rec.paper.id.lower() == key:
                return k
            if rec.paper.doi and rec.paper.doi.lower() == key:
                return k
        return None

    def screen_paper(
        self, paper_id: str, decision: ScreeningDecision, reason: str = ""
    ) -> None:
        """Record a screening decision for a paper."""
        key = self._find_key(paper_id)
        if key:
            self.records[key].screening_decision = decision
            self.records[key].rejection_reason = reason

    def screen_batch(
        self, decisions: dict[str, ScreeningDecision]
    ) -> None:
        """Batch screening: {paper_id: decision}."""
        for pid, decision in decisions.items():
            self.screen_paper(pid, decision)

    def get_included_papers(self) -> list[Paper]:
        """Get all papers that passed screening."""
        return [
            r.paper for r in self.records.values()
            if r.screening_decision == ScreeningDecision.ACCEPT
        ]

    def get_accepted_ids(self) -> set[str]:
        """Get IDs of accepted papers."""
        return {
            pid for pid, r in self.records.items()
            if r.screening_decision == ScreeningDecision.ACCEPT
        }

    def generate_report(self) -> PRISMAReport:
        """Generate a PRISMA 2020 flow report from current state."""
        report = PRISMAReport()

        # Count by source
        for r in self.records.values():
            if r.source == "database_search":
                report.database_results += 1
            elif r.source == "snowballing":
                report.snowball_results += 1
            elif r.source == "similar":
                report.similar_results += 1
            elif r.source == "manual":
                report.manual_additions += 1

        report.records = list(self.records.values())
        report.records_after_dedup = len(self.records)
        report.records_screened = sum(
            1 for r in self.records.values()
            if r.screening_decision != ScreeningDecision.PENDING
        )
        report.records_excluded_title_abstract = sum(
            1 for r in self.records.values()
            if r.screening_decision == ScreeningDecision.REJECT
        )
        report.full_text_assessed = sum(
            1 for r in self.records.values()
            if r.screening_decision == ScreeningDecision.ACCEPT
        )
        report.studies_included = report.full_text_assessed

        # Exclusion reasons
        reasons: dict[str, int] = defaultdict(int)
        for r in self.records.values():
            if r.screening_decision == ScreeningDecision.REJECT and r.rejection_reason:
                reasons[r.rejection_reason] += 1
        report.full_text_exclusion_reasons = dict(reasons)

        return report
