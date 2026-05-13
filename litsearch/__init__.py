"""Literature Relationship Network Explorer."""

__version__ = "0.2.0"

from litsearch.models import Paper, Author, CitationNetwork, SearchResult
from litsearch.search import LiteratureExplorer
from litsearch.cache import Cache
from litsearch.sources import SourceManager
from litsearch.path_miner import EvolutionPathMiner, EvolutionPath, EraHub, EvolutionLink
from litsearch.downloader import PaperDownloader

__all__ = [
    "Paper",
    "Author",
    "CitationNetwork",
    "SearchResult",
    "LiteratureExplorer",
    "Cache",
    "SourceManager",
    "EvolutionPathMiner",
    "EvolutionPath",
    "EraHub",
    "EvolutionLink",
    "PaperDownloader",
]
