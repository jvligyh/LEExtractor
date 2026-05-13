"""Unified data models for literature search results."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Author:
    name: str
    author_id: Optional[str] = None


@dataclass
class Paper:
    """Unified paper representation across all data sources."""

    id: str  # Canonical ID: DOI if available, else S2 ID or OpenAlex ID
    title: str
    abstract: Optional[str] = None
    authors: list[Author] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    citation_count: int = 0
    reference_count: int = 0
    citation_ids: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    source: str = ""  # "semantic_scholar" | "openalex" | "crossref"
    url: Optional[str] = None
    relevance_score: float = 0.0
    topics: list[str] = field(default_factory=list)


@dataclass
class CitationNetwork:
    """Wraps a NetworkX DiGraph with metadata about the citation network."""

    seed_paper_id: str
    papers: dict[str, "Paper"] = field(default_factory=dict)
    hop_depth: int = 0
    central_papers: list[str] = field(default_factory=list)
    clusters: dict[int, list[str]] = field(default_factory=dict)
    graph_data: Optional[dict] = None  # node-link JSON for serialization

    @property
    def node_count(self) -> int:
        return len(self.papers)

    @property
    def edge_count(self) -> int:
        if self.graph_data is None:
            return 0
        return len(self.graph_data.get("links", []))


@dataclass
class SearchResult:
    """Result of a literature search operation."""

    papers: list[Paper] = field(default_factory=list)
    network: Optional[CitationNetwork] = None
    trend_metrics: dict = field(default_factory=dict)
    total_available: int = 0
    elapsed_seconds: float = 0.0
