from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from app.schemas.company_evidence import CompanyEvidence
from app.schemas.company_trust import TrustReport
from app.schemas.job import Job
from app.services.company.collector import collect_company_evidence
from app.services.company.deterministic_trust import (
    SCAM_KEYWORDS,
    calculate_deterministic_trust,
)
from app.services.company.analyzer import analyze_company


_HIDDEN_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "svg",
    "noscript",
}

_JOB_BOARD_DOMAINS = {
    "indeed.com",
    "glassdoor.com",
    "naukri.com",
    "ziprecruiter.com",
    "monster.com",
    "simplyhired.com",
    "talent.com",
    "careerbuilder.com",
    "jooble.org",
    "wellfound.com",
}


class _EvidenceTextParser(HTMLParser):
    """Extract readable text without HTML markup or embedded code."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._hidden_tags = []

    def handle_starttag(self, tag, attrs):
        if self._hidden_tags:
            if tag in _HIDDEN_TAGS:
                self._hidden_tags.append(tag)
        elif tag in _HIDDEN_TAGS:
            self._hidden_tags.append(tag)

    def handle_endtag(self, tag):
        for index in range(
            len(self._hidden_tags) - 1, -1, -1
        ):
            if self._hidden_tags[index] == tag:
                del self._hidden_tags[index:]
                break

    def handle_data(self, data):
        if not self._hidden_tags:
            self.parts.append(data)


def _clean_evidence_text(
    value: str | None,
    max_length: int = 300,
) -> str:
    """Remove markup, normalize whitespace, and limit snippet length."""

    parser = _EvidenceTextParser()

    try:
        parser.feed(value or "")
        parser.close()
        text = " ".join(parser.parts)
    except Exception:
        # Do not expose malformed source markup.
        text = ""

    # Remove escaped Markdown characters such as \####.
    text = re.sub(
        r"\\([#>*_`~\[\]()|])",
        r"\1",
        text,
    )

    # Convert Markdown links and images into readable labels.
    text = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        r"\1",
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    # Remove Markdown headings and formatting characters.
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"[*`~]", "", text)
    text = re.sub(
        r"(?<!\w)_{1,3}|_{1,3}(?!\w)",
        "",
        text,
    )

    # Remove remaining tag-like markup.
    text = re.sub(
        r"</?[a-z][^>]*>",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = " ".join(text.split()).strip()

    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "…"

    return text


def _safe_http_url(value: str | None) -> str | None:
    """Accept only normal HTTP or HTTPS URLs."""

    value = (value or "").strip()

    try:
        parsed = urlparse(value)

        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None

        return value

    except ValueError:
        return None


def _is_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _eligible_company_url(
    kind: str,
    raw_url: str | None,
) -> str | None:
    """Avoid presenting job-board URLs as official company pages."""

    url = _safe_http_url(raw_url)

    if not url:
        return None

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host.startswith("www."):
        host = host[4:]

    if kind == "linkedin":
        # Only identify actual LinkedIn company pages as LinkedIn evidence.
        if not _is_domain(host, "linkedin.com"):
            return None

        if "/company/" not in parsed.path.lower():
            return None

        return url

    # Job boards and LinkedIn must not be labeled as an official website
    # or an official careers page.
    if _is_domain(host, "linkedin.com"):
        return None

    if any(
        _is_domain(host, domain)
        for domain in _JOB_BOARD_DOMAINS
    ):
        return None

    return url


def build_company_evidence_summary(
    evidence: CompanyEvidence,
) -> dict:
    """Return a readable report while separating missing data from risks."""

    available = []
    unavailable = []
    search_results = []
    risk_signals = []
    seen_risk_signals = set()

    company_links = [
        (
            "official_website",
            "Official website",
            evidence.official_website,
        ),
        (
            "linkedin",
            "LinkedIn company page",
            evidence.linkedin_url,
        ),
        (
            "careers_page",
            "Careers page",
            evidence.careers_page,
        ),
    ]

    for kind, label, raw_url in company_links:
        url = _eligible_company_url(kind, raw_url)

        if url:
            if kind == "official_website":
                summary = (
                    "A potential official website URL was found. "
                    "Company ownership has not been independently verified."
                )
            elif kind == "linkedin":
                summary = (
                    "A LinkedIn company-page URL was found in the evidence."
                )
            else:
                summary = (
                    "A potential careers-page URL was found. "
                    "Its relationship to the company has not been "
                    "independently verified."
                )

            available.append({
                "kind": kind,
                "label": label,
                "url": url,
                "summary": summary,
            })

        else:
            unavailable.append({
                "kind": kind,
                "label": label,
                "summary": (
                    f"No eligible {label.lower()} URL was found "
                    "in the collected evidence. This is missing "
                    "evidence, not proof of fraud."
                ),
            })

    for item in evidence.evidence_items:
        raw_snippet = item.snippet or ""

        title = (
            _clean_evidence_text(item.title, 140)
            or "Search result"
        )

        snippet = _clean_evidence_text(raw_snippet, 300)
        url = _safe_http_url(item.url)

        source = getattr(
            item.source,
            "value",
            str(item.source),
        )

        search_results.append({
            "kind": "search_result",
            "source": source,
            "title": title,
            "url": url,
            "summary": snippet or "No readable summary was available.",
            "confidence": item.confidence,
        })

        # Risk indicators must be tied to an actual source snippet.
        snippet_lower = raw_snippet.lower()

        for keyword in SCAM_KEYWORDS:
            if keyword not in snippet_lower:
                continue

            signal_key = (keyword, url or title)

            if signal_key in seen_risk_signals:
                continue

            seen_risk_signals.add(signal_key)

            risk_signals.append({
                "kind": "recruitment_risk_phrase",
                "matched_phrase": keyword,
                "summary": (
                    f'The collected search snippet contains '
                    f'the phrase "{keyword}". Review the source '
                    "before treating this as a confirmed risk."
                ),
                "source_title": title,
                "source_url": url,
                "source_summary": snippet,
            })

    if not search_results:
        unavailable.append({
            "kind": "search_results",
            "label": "Public search results",
            "summary": (
                "No public search results were returned. "
                "This is unavailable evidence, not proof of fraud."
            ),
        })

    return {
        "company_name": _clean_evidence_text(
            evidence.company_name,
            140,
        ),
        "available": available,
        "unavailable": unavailable,
        "search_results": search_results,
        "risk_signals": risk_signals,
    }


def get_company_trust_with_evidence(
    job: Job,
) -> tuple[TrustReport, CompanyEvidence]:
    print(f"\n--- Gathering Evidence for: {job.company} ---")

    evidence = collect_company_evidence(job)

    print(f"Website found: {bool(evidence.official_website)}")
    print(f"LinkedIn found: {bool(evidence.linkedin_url)}")
    print(f"Careers found: {bool(evidence.careers_page)}")

    # Keep the existing trust-scoring logic unchanged.
    report = calculate_deterministic_trust(evidence)

    if report.trust_score >= 60:
        print(
            f"[{job.company}] Using Deterministic Trust. "
            f"Score: {report.trust_score}"
        )
        return report, evidence

    print(
        f"[{job.company}] Deterministic score too low "
        f"({report.trust_score}). Falling back to LLM deep scan..."
    )

    try:
        return analyze_company(evidence), evidence
    except Exception as error:
        print(
            f"LLM Analysis failed: {error}. "
            "Returning deterministic score anyway."
        )
        return report, evidence


def get_company_trust(job: Job) -> TrustReport:
    """Preserve the existing TrustReport-only interface."""

    report, _ = get_company_trust_with_evidence(job)
    return report