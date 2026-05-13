"""Systematic Literature Review Toolkit — LEExtractor."""

__version__ = "0.3.0"

from litsearch.models import Paper, Author, CitationNetwork, SearchResult
from litsearch.search import (
    LiteratureReviewWorkflow,
    LiteratureExplorer,
    ReviewState,
    ReviewPhase,
)
from litsearch.cache import Cache
from litsearch.sources import SourceManager, ImpactFactorLookup
from litsearch.path_miner import EvolutionPathMiner, EvolutionPath, EraHub, EvolutionLink
from litsearch.snowball import SnowballEngine, SnowballResult, SnowballRound
from litsearch.similar import SimilarPaperFinder
from litsearch.prisma import (
    PRISMATracker,
    PRISMARecord,
    PRISMAReport,
    ScreeningDecision,
)
from litsearch.downloader import PaperDownloader

__all__ = [
    # Models
    "Paper",
    "Author",
    "CitationNetwork",
    "SearchResult",
    # Workflow
    "LiteratureReviewWorkflow",
    "LiteratureExplorer",
    "ReviewState",
    "ReviewPhase",
    # Infrastructure
    "Cache",
    "SourceManager",
    "ImpactFactorLookup",
    # Evolution (legacy)
    "EvolutionPathMiner",
    "EvolutionPath",
    "EraHub",
    "EvolutionLink",
    # Snowballing
    "SnowballEngine",
    "SnowballResult",
    "SnowballRound",
    # Similar papers
    "SimilarPaperFinder",
    # PRISMA
    "PRISMATracker",
    "PRISMARecord",
    "PRISMAReport",
    "ScreeningDecision",
    # Download
    "PaperDownloader",
]
