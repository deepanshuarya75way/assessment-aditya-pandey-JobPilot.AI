from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from app.api.dependencies import (
    get_current_user,
)

from app.schemas.api.job_search import (
    JobSearchRequest,
)

from app.schemas.api.application import (
    ApplicationRequest,
)

from app.schemas.api.application_status import (
    ApplicationStatusRequest,
)

from app.schemas.api.job_search import JobAnalyzeRequest
from app.services.resume.extractor import extract_resume
from app.services.resume.job_matcher import match_resume_to_job
from app.services.company.job_trust import (
    build_company_evidence_summary,
    get_company_trust_with_evidence,
)

from app.schemas.api.responses import (
    JobSearchResponse,
    JobListResponse,
    JobDetailResponse,
    ApplicationResponse,
    ApplicationListResponse,
    ApplicationDetailResponse,
    ApplicationStatusResponse,
)

from app.graphs.orchestrator import (
    master_orchestrator,
)

from app.repositories.jobs import (
    save_job,
    get_job,
    get_jobs,
)

from app.repositories.applications import (
    save_application,
    get_applications,
    get_application,
    update_application_status,
)


router = APIRouter(
    prefix="/api/jobs",
    tags=["Jobs"],
)


# ============================================================
# SEARCH JOBS
# ============================================================

@router.post(
    "/search",
    response_model=JobSearchResponse,
)
async def search_jobs(
    request: Request,
    data: JobSearchRequest,
):

    try:

        from app.services.resume.extractor import (
            extract_resume,
        )

        resume = extract_resume(
            data.resume_text
        )

        result = await master_orchestrator.ainvoke({

            "operation": "rank",

            "user_query": data.query,

            "resume": resume,

            "discovered_jobs": [],

            "ranked_jobs": [],

            "selected_job": None,

            "application_report": None,
        })

        ranked_jobs = result[
            "ranked_jobs"
        ]

        database = request.app.state.database

        for ranked_job in ranked_jobs:

            await save_job(
                database,
                ranked_job.job,
            )

        return {
            "success": True,
            "count": len(ranked_jobs),
            "jobs": ranked_jobs,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Job search failed",
        ) from error


# ============================================================
# GET SAVED JOBS
# ============================================================

@router.get(
    "",
    response_model=JobListResponse,
)
async def list_jobs(
    request: Request,
    limit: int = 50,
    offset: int = 0,
):

    if limit < 1 or limit > 100:

        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    if offset < 0:

        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative",
        )

    try:

        database = request.app.state.database

        jobs = await get_jobs(
            database,
            limit=limit,
            offset=offset,
        )

        return {
            "success": True,
            "count": len(jobs),
            "limit": limit,
            "offset": offset,
            "jobs": jobs,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve jobs",
        ) from error


# ============================================================
# GET JOB DETAILS
# ============================================================

@router.get(
    "/detail/{source}/{external_id}",
    response_model=JobDetailResponse,
)
async def get_job_details(
    request: Request,
    source: str,
    external_id: str,
):

    try:

        database = request.app.state.database

        job = await get_job(
            database,
            external_id,
            source,
        )

        if job is None:

            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        return {
            "success": True,
            "job": job,
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve job",
        ) from error


# ============================================================
# GENERATE APPLICATION
# ============================================================

@router.post(
    "/application",
    response_model=ApplicationResponse,
)
async def generate_application(
    request: Request,
    data: ApplicationRequest,
    user=Depends(
        get_current_user
    ),
):

    try:

        database = request.app.state.database

        job = await get_job(
            database,
            external_id=data.external_id,
            source=data.source,
        )

        if job is None:

            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        from app.services.resume.extractor import (
            extract_resume,
        )

        resume = extract_resume(
            data.resume_text
        )

        result = await master_orchestrator.ainvoke({

            "operation": "apply",

            "user_query": "",

            "resume": resume,

            "discovered_jobs": [],

            "ranked_jobs": [],

            "selected_job": job,

            "application_report": None,
        })

        application_report = result[
            "application_report"
        ]

        application_id = await save_application(
            database,
            user["_id"],
            job,
            resume,
            application_report,
        )

        return {
            "success": True,
            "application_id": application_id,
            "application": application_report,
        }

    except HTTPException:
        raise

    except Exception as error:
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(error)}",
        )


# ============================================================
# GET USER APPLICATIONS
# ============================================================

@router.get(
    "/applications",
    response_model=ApplicationListResponse,
)
async def list_applications(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    user=Depends(
        get_current_user
    ),
):

    if limit < 1 or limit > 100:

        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    if offset < 0:

        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative",
        )

    valid_statuses = {
        "saved",
        "applied",
        "assessment",
        "interview",
        "offer",
        "rejected",
    }

    if status is not None and status not in valid_statuses:

        raise HTTPException(
            status_code=400,
            detail="Invalid application status",
        )

    try:

        database = request.app.state.database

        applications = await get_applications(
            database,
            user["_id"],
            limit=limit,
            offset=offset,
            status=status,
        )

        return {
            "success": True,
            "count": len(applications),
            "limit": limit,
            "offset": offset,
            "applications": applications,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve applications",
        ) from error


# ============================================================
# GET APPLICATION DETAILS
# ============================================================

@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetailResponse,
)
async def get_application_details(
    request: Request,
    application_id: str,
    user=Depends(
        get_current_user
    ),
):

    try:

        database = request.app.state.database

        application = await get_application(
            database,
            user["_id"],
            application_id,
        )

        if application is None:

            raise HTTPException(
                status_code=404,
                detail="Application not found",
            )

        return {
            "success": True,
            "application": application,
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve application",
        ) from error


# ============================================================
# UPDATE APPLICATION STATUS
# ============================================================

@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationStatusResponse,
)
async def update_status(
    request: Request,
    application_id: str,
    data: ApplicationStatusRequest,
    user=Depends(
        get_current_user
    ),
):

    try:

        database = request.app.state.database

        updated = await update_application_status(
            database,
            user["_id"],
            application_id,
            data.status,
        )

        if not updated:

            raise HTTPException(
                status_code=404,
                detail="Application not found",
            )

        application = await get_application(
            database,
            user["_id"],
            application_id,
        )

        return {
            "success": True,
            "application": application,
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Unable to update application",
        ) from error


@router.post("/detail/{source}/{external_id}/analyze")
async def analyze_single_job(
    request: Request,
    source: str,
    external_id: str,
    data: JobAnalyzeRequest,
):
    try:
        database = request.app.state.database

        job = await get_job(
            database,
            external_id=external_id,
            source=source,
        )

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        # 1. Parse candidate resume.
        resume = extract_resume(data.resume_text)

        # 2. Compute ATS resume match and missing skills.
        resume_match_report = match_resume_to_job(resume, job)

        # 3. Compute company trust and collect evidence once.
        company_trust_report, company_evidence = (
            get_company_trust_with_evidence(job)
        )

        # 4. Return the existing trust result plus readable evidence.
        return {
            "success": True,
            "job": job,
            "ats_match": resume_match_report,
            "company_trust": company_trust_report,
            "company_evidence": build_company_evidence_summary(
                company_evidence
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(error)}",
        ) from error

# ============================================================
# GENERATE INTERVIEW PREP
# ============================================================

@router.post(
    "/applications/{application_id}/interview-prep",
)
async def generate_interview_prep(
    request: Request,
    application_id: str,
    user=Depends(get_current_user),
):
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    import os
    from dotenv import load_dotenv

    try:
        # Load environment variables to expose GROQ_API_KEY
        load_dotenv()
        
        database = request.app.state.database
        
        # 1. Fetch the saved application
        application = await get_application(
            database, 
            user["_id"], 
            application_id
        )
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # 2. NEW: Fetch the user's Master Resume from the database
        db_user = await database["users"].find_one({"_id": user["_id"]})
        resume_text = db_user.get("resume_text", "") if db_user else ""

        # Extract job details safely
        job_title = application.get("job", {}).get("title", "the role")
        job_desc = application.get("job", {}).get("description", "")
        
        # Initialize Groq 
        # (Note: make sure you use a valid Groq model here, like "llama3-70b-8192" or "mixtral-8x7b-32768")
        llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model="openai/gpt-oss-120b", 
        )
        
        # 3. NEW: The highly detailed prompt instructing strict formatting and resume alignment
        system_prompt = """You are an expert Technical Recruiter and Interview Coach.
Your task is to generate a highly personalized interview guide based on the provided Job Description and the Candidate's Resume.

CRITICAL FORMATTING RULES:
1. NO ASTERISKS ALLOWED: Do NOT use any asterisks (*) or markdown bold/italics symbols anywhere in your response. 
2. PLAIN TEXT HEADERS: Use clean uppercase text or dashes for section titles instead of markdown.
3. QUESTION ALIGNMENT: Questions must be directly tied to the core technical and business requirements in the Job Description.
4. ANSWER ALIGNMENT: The strategy MUST explicitly reference the candidate's actual past experiences, projects, or tools from their Resume.
5. DETAIL LEVEL: Provide a detailed, 3-to-4 sentence answer strategy using the STAR method (Situation, Task, Action, Result).

STRICT LAYOUT TO FOLLOW:

TECHNICAL QUESTION 1
Question: [Insert specific technical question based on the JD]
Suggested Answer Strategy: [Write a detailed 3-4 sentence strategy using the candidate's specific resume experience.]

TECHNICAL QUESTION 2
Question: [Insert specific technical question based on the JD]
Suggested Answer Strategy: [Write a detailed 3-4 sentence strategy using the candidate's specific resume experience.]

TECHNICAL QUESTION 3
Question: [Insert specific technical question based on the JD]
Suggested Answer Strategy: [Write a detailed 3-4 sentence strategy using the candidate's specific resume experience.]

BEHAVIORAL QUESTION 1
Question: [Insert specific behavioral question based on the JD's soft skills]
Suggested Answer Strategy: [Write a detailed 3-4 sentence strategy mapping a past scenario from the resume to this question.]

BEHAVIORAL QUESTION 2
Question: [Insert specific behavioral question based on the JD's soft skills]
Suggested Answer Strategy: [Write a detailed 3-4 sentence strategy mapping a past scenario from the resume to this question.]
"""

        # Build the prompt injecting the JD AND the Resume
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", f"Role: {job_title}\n\nJob Description: {job_desc}\n\nCandidate Resume: {resume_text}")
        ])
        
        # Execute the chain
        chain = prompt | llm
        response = await chain.ainvoke({})
        
        return {
            "success": True,
            "prep_guide": response.content
        }
        
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(error))
    

# ============================================================
# USER PROFILE / RESUME
# ============================================================
from pydantic import BaseModel

class ProfileRequest(BaseModel):
    resume_text: str

@router.get("/profile")
async def get_profile(
    request: Request,
    user=Depends(get_current_user)
):
    database = request.app.state.database
    user_doc = await database["users"].find_one({"_id": user["_id"]})
    resume_text = user_doc.get("resume_text", "") if user_doc else ""
    
    return {"success": True, "resume_text": resume_text}

@router.post("/profile")
async def save_profile(
    request: Request,
    data: ProfileRequest,
    user=Depends(get_current_user)
):
    database = request.app.state.database
    await database["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"resume_text": data.resume_text}},
        upsert=True
    )
    return {"success": True, "message": "Resume saved successfully"}

# ============================================================
# AUTO-APPLY AGENT
# ============================================================
from pydantic import BaseModel

class AutoApplyRequest(BaseModel):
    job_url: str
    first_name: str
    last_name: str
    email: str
    phone: str
    linkedin: str = ""

# ============================================================
# AUTO-APPLY AGENT
# ============================================================
from pydantic import BaseModel

class AutoApplyRequest(BaseModel):
    job_url: str
    first_name: str
    last_name: str
    email: str
    phone: str
    linkedin: str = ""

# ============================================================
# AUTO-APPLY AGENT
# ============================================================
# ============================================================
# AUTO-APPLY AGENT
# ============================================================
@router.post("/applications/{application_id}/auto-apply")
async def trigger_auto_apply(
    request: Request,
    application_id: str,
    user=Depends(get_current_user)
):
    from bson import ObjectId
    from fastapi.concurrency import run_in_threadpool
    from app.services.automation.apply_agent import auto_apply_master
    
    database = request.app.state.database
    
    # 1. Fetch the application to get the job URL
    application = await get_application(database, user["_id"], application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
        
    job_data = application.get("job", {})
    job_url = job_data.get("apply_url") or job_data.get("source_url") or ""
    
    if not job_url:
        raise HTTPException(status_code=400, detail="No job URL found for this application.")

    # 2. Safely resolve the user document using ObjectId conversion
    raw_user_id = user.get("_id") or user.get("id")
    query_id = ObjectId(str(raw_user_id)) if ObjectId.is_valid(str(raw_user_id)) else raw_user_id

    user_doc = user if user.get("name") else await database["users"].find_one({"_id": query_id})
    if not user_doc and user.get("email"):
        user_doc = await database["users"].find_one({"email": user["email"]})

    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # 3. Split the single 'name' field
    full_name = user_doc.get("name", "").strip()
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0] if len(name_parts) > 0 else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    real_profile_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": user_doc.get("email", ""),
        "phone": user_doc.get("phone", ""),
        "linkedin": user_doc.get("linkedin", "")
    }
    
    # 4. Run browser automation in background thread
    result = await run_in_threadpool(auto_apply_master, job_url, real_profile_data)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Automation failed"))
        
    return {"success": True, "message": result.get("message", "Application processed")}