from app.schemas.company_evidence import CompanyEvidence
from app.schemas.company_trust import TrustReport, TrustBreakdown
from app.services.company.url_utils import get_domain

SCAM_KEYWORDS = [
    "registration fee",
    "pay advance",
    "training fee",
    "security deposit",
    "refundable fee",
    "money for job",
    "whatsapp interview",
    "telegram interview",
    "pay to apply",
    "processing fee",
]


def calculate_deterministic_trust(
    evidence: CompanyEvidence,
) -> TrustReport:
    company_lower = evidence.company_name.lower().replace(" ", "")

    # 1. Website Score (Max 25)
    website_score = 0

    if evidence.official_website:
        domain = get_domain(
            evidence.official_website
        ).replace(".", "")

        if any(
            word in domain
            for word in company_lower.split()
            if len(word) > 2
        ):
            website_score = 25
        else:
            website_score = 15

    # 2. LinkedIn Score (Max 20)
    linkedin_score = 0
    scale_tier = "Standard / Startup"

    if evidence.linkedin_url:
        linkedin_score = 15

        for item in evidence.evidence_items:
            snippet = (item.snippet or "").lower()

            if any(
                term in snippet
                for term in [
                    "1m+ followers",
                    "10m+ followers",
                    "million followers",
                    "billion",
                    "fortune 500",
                    "multinational",
                ]
            ):
                linkedin_score = 20
                scale_tier = "Global Enterprise"
                break

            elif any(
                term in snippet
                for term in [
                    "k followers",
                    "10,000+ employees",
                    "5,000+ employees",
                ]
            ):
                linkedin_score = 20
                scale_tier = "Mid-Size Corporate"
                break

    # Enforce the schema limit.
    linkedin_score = max(0, min(linkedin_score, 20))

    # 3. Careers Score (Max 20)
    careers_score = 15 if evidence.careers_page else 5

    # 4. Public Presence Score (Max 20)
    public_presence_score = min(
        len(evidence.evidence_items) * 3,
        20,
    )

    # 5. Evidence Quality Score (Max 15)
    evidence_quality_score = 15
    red_flags = []
    strengths = []
    scam_detected = False

    for item in evidence.evidence_items:
        snippet_lower = (item.snippet or "").lower()

        for keyword in SCAM_KEYWORDS:
            if keyword in snippet_lower:
                scam_detected = True
                red_flags.append(
                    f"Suspicious phrase found in web search: '{keyword}'"
                )

    if scam_detected:
        evidence_quality_score = max(
            0,
            evidence_quality_score - 20,
        )

        red_flags.append(
            "Warning: Web search indicates potential recruitment fraud indicators."
        )

    trust_score = max(
        0,
        min(
            website_score
            + linkedin_score
            + careers_score
            + public_presence_score
            + evidence_quality_score,
            100,
        ),
    )

    confidence = min(
        50 + len(evidence.evidence_items) * 5,
        95,
    )

    if scam_detected or trust_score < 50:
        recommendation = "High Risk"
    elif trust_score >= 85:
        recommendation = "Trusted"
    elif trust_score >= 70:
        recommendation = "Mostly Trusted"
    elif trust_score >= 50:
        recommendation = "Use Caution"
    else:
        recommendation = "Suspicious"

    if website_score == 25:
        strengths.append(
            "Verified official corporate domain match"
        )

    if linkedin_score >= 20:
        strengths.append(
            f"Established {scale_tier} presence with strong organizational scale"
        )
    else:
        strengths.append(
            "Verified active corporate footprint"
        )

    if evidence.careers_page:
        strengths.append(
            "Active corporate careers portal detected"
        )

    if not evidence.official_website:
        red_flags.append(
            "Official website could not be deterministically verified"
        )

    summary = (
        f"{evidence.company_name} received a trust score of "
        f"{trust_score}% based on live web search and enterprise scaling analysis."
    )

    reasoning = (
        f"Evaluated as a {scale_tier} using domain matching, "
        "live search footprint, and scam keyword filters."
    )

    return TrustReport(
        trust_score=trust_score,
        confidence=confidence,
        recommendation=recommendation,
        breakdown=TrustBreakdown(
            website_score=website_score,
            linkedin_score=linkedin_score,
            careers_score=careers_score,
            public_presence_score=public_presence_score,
            evidence_quality_score=evidence_quality_score,
        ),
        strengths=strengths,
        red_flags=red_flags,
        summary=summary,
        reasoning=reasoning,
    )