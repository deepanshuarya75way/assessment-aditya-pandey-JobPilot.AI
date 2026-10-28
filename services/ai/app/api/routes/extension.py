from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from bson import ObjectId

from app.api.dependencies import get_current_user
from app.schemas.job import Job
from app.services.company.job_trust import (
    build_company_evidence_summary,
    get_company_trust_with_evidence,
)
from app.graphs.application import application_graph


router = APIRouter(
    prefix="/extension",
    tags=["Chrome Extension"],
)


class ExtensionAnalyzeRequest(BaseModel):
    job_title: str
    company_name: str
    job_description: str
    page_url: str


@router.get("/profile")
async def get_extension_profile(
    request: Request,
    user=Depends(get_current_user),
):
    database = request.app.state.database

    raw_user_id = user.get("_id") or user.get("id")
    query_id = (
        ObjectId(str(raw_user_id))
        if ObjectId.is_valid(str(raw_user_id))
        else raw_user_id
    )

    user_doc = (
        user
        if user.get("name")
        else await database["users"].find_one({"_id": query_id})
    )

    if not user_doc and user.get("email"):
        user_doc = await database["users"].find_one(
            {"email": user["email"]}
        )

    if not user_doc:
        raise HTTPException(
            status_code=404,
            detail="User profile not found",
        )

    full_name = user_doc.get("name", "").strip()
    name_parts = full_name.split(" ", 1)

    return {
        "first_name": name_parts[0] if len(name_parts) > 0 else "",
        "last_name": name_parts[1] if len(name_parts) > 1 else "",
        "full_name": full_name,
        "email": user_doc.get("email", ""),
        "phone": user_doc.get("phone", ""),
        "linkedin": user_doc.get("linkedin", ""),
    }


# 1. Independent job and company trust analysis.
@router.post("/analyze-job")
async def analyze_job_only(
    request: Request,
    payload: ExtensionAnalyzeRequest,
    user=Depends(get_current_user),
):
    if (
        not payload.job_description
        or len(payload.job_description.strip()) < 40
    ):
        raise HTTPException(
            status_code=400,
            detail="Job description text is too short to analyze.",
        )

    job_stub = Job(
        title=payload.job_title,
        company=payload.company_name,
        description=payload.job_description,
        url=payload.page_url,
        external_id="extension-scan",
        source="adzuna",
        location="Unknown",
        apply_url=payload.page_url,
    )

    # Collect evidence once and reuse it for the trust report.
    trust_report, evidence = get_company_trust_with_evidence(job_stub)

    company_evidence = build_company_evidence_summary(evidence)

    # Keep the existing extension response fields for compatibility.
    company_links = {
        item["kind"]: item["url"]
        for item in company_evidence["available"]
    }

    is_safe_company = trust_report.recommendation not in [
        "Suspicious",
        "High Risk",
    ]

    return {
        "success": True,
        "job_title": payload.job_title,
        "company": payload.company_name,
        "company_trust": {
            "score": trust_report.trust_score,
            "recommendation": trust_report.recommendation,
            "red_flags": trust_report.red_flags,
            "strengths": trust_report.strengths,
            "is_safe": is_safe_company,
            "official_website": company_links.get("official_website"),
            "careers_page": company_links.get("careers_page"),
            "linkedin_url": company_links.get("linkedin"),
        },
        "company_evidence": company_evidence,
    }


# 2. Independent resume-fit analysis.
@router.post("/analyze-fit")
async def analyze_resume_fit(
    request: Request,
    payload: ExtensionAnalyzeRequest,
    user=Depends(get_current_user),
):
    if (
        not payload.job_description
        or len(payload.job_description.strip()) < 40
    ):
        raise HTTPException(
            status_code=400,
            detail="Job description text is too short to analyze.",
        )

    # 1. Fetch the user's master resume from MongoDB.
    database = request.app.state.database
    raw_user_id = user.get("_id") or user.get("id")

    user_id = (
        ObjectId(str(raw_user_id))
        if ObjectId.is_valid(str(raw_user_id))
        else raw_user_id
    )

    user_doc = await database["users"].find_one({"_id": user_id})

    resume_text = (
        user_doc.get(
            "resume_text",
            "Python, FastAPI, Backend development experience.",
        )
        if user_doc
        else ""
    )

    # 2. Create the Job object required by the application graph.
    job_stub = Job(
        title=payload.job_title,
        company=payload.company_name,
        description=payload.job_description,
        url=payload.page_url,
        external_id="extension-scan",
        source="adzuna",
        location="Unknown",
        apply_url=payload.page_url,
    )

    # 3. Run the existing application pipeline.
    result = await application_graph.ainvoke({
        "job": job_stub,
        "resume": resume_text,
        "analysis": None,
        "tailored_resume": None,
        "cover_letter": None,
        "checklist": None,
    })

    # 4. Extract the graph's output.
    analysis = result.get("analysis")
    cover_letter = result.get("cover_letter")
    tailored_resume = result.get("tailored_resume")

    cover_letter_text = getattr(
        cover_letter,
        "content",
        str(cover_letter),
    )

    tailored_text = getattr(
        tailored_resume,
        "summary",
        str(tailored_resume),
    )

    return {
        "success": True,
        "job_title": payload.job_title,
        "company": payload.company_name,
        "resume_fit": {
            "overall_fit_score": getattr(
                analysis,
                "fit_score",
                85,
            ),
            "missing_skills": getattr(
                analysis,
                "missing_skills",
                [],
            ),
            "cover_letter": cover_letter_text,
            "tailored_resume": tailored_text,
        },
    }