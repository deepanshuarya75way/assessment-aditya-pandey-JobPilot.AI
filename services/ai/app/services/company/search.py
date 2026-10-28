from math import isfinite

from tavily import TavilyClient

from app.core.config import settings
from app.schemas.evidence import EvidenceItem
from app.schemas.evidence_source import EvidenceSource


client = TavilyClient(
    api_key=settings.tavily_api_key
)


def search_company(
    company: str,
) -> list[EvidenceItem]:

    response = client.search(
        query=f"{company} official website linkedin careers",
        search_depth="advanced",
        max_results=8,
    )

    evidence = []

    for item in response.get("results", []):
        # Use Tavily's actual relevance score instead of fixed 0.8.
        try:
            score = float(item.get("score", 0.0))

            if not isfinite(score):
                score = 0.0

        except (TypeError, ValueError):
            score = 0.0

        # Keep the score within the EvidenceItem schema limits.
        score = max(0.0, min(score, 1.0))

        evidence.append(
            EvidenceItem(
                source=EvidenceSource.SEARCH,
                title=item["title"],
                url=item["url"],
                snippet=item["content"],
                confidence=score,
            )
        )

    return evidence