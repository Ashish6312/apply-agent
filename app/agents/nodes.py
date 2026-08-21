"""LangGraph node functions.

Each node takes the current AgentState and returns a dict of updated keys.
Nodes are kept thin - they call services/ for actual work (parsing, LLM
extraction, matching, scoring) and are responsible for: wiring inputs to
the right service, handling errors gracefully, and appending to the
execution trace so the workflow's behavior is visible in the UI.
"""
import logging

from app.schemas.analysis import Recommendation
from app.schemas.job import JobRequirements
from app.schemas.resume import CandidateProfile
from app.services import application_generator, job_analyzer, profile_extractor, resume_parser, scoring
from app.services.resume_parser import ResumeParsingError
from app.services.skill_matcher import match_skills

logger = logging.getLogger(__name__)


def _log(state: dict, message: str) -> list[str]:
    """Append to the execution trace. Returns the new list (LangGraph replaces
    the state key wholesale, it does not auto-merge lists)."""
    trace = list(state.get("execution_trace", []))
    trace.append(message)
    logger.info(message)
    return trace


def _log_error(state: dict, message: str) -> list[str]:
    errors = list(state.get("errors", []))
    errors.append(message)
    logger.warning(message)
    return errors


def parse_resume(state: dict) -> dict:
    """Deterministic PDF -> text, then LLM structured extraction into CandidateProfile."""
    errors = list(state.get("errors", []))
    trace = state.get("execution_trace", [])

    try:
        resume_text = resume_parser.extract_text(state["resume_bytes"])
    except ResumeParsingError as exc:
        errors.append(f"Resume parsing failed: {exc}")
        return {
            "resume_text": "",
            "candidate_profile": CandidateProfile(),
            "resume_extraction_failed": True,
            "execution_trace": _log(state, f"Resume parsing failed: {exc}"),
            "errors": errors,
        }

    trace = _log(state, "Resume parsed successfully")

    try:
        candidate_profile = profile_extractor.extract_candidate_profile(resume_text)
        trace = trace + [f"Extracted {len(candidate_profile.skills)} candidate skills"]
        extraction_failed = False
    except Exception as exc:  # LLM call can fail in many provider-specific ways
        errors.append(f"Resume skill extraction failed: {exc}")
        candidate_profile = CandidateProfile()
        trace = trace + [f"Resume skill extraction failed, continuing with empty profile: {exc}"]
        extraction_failed = True

    return {
        "resume_text": resume_text,
        "candidate_profile": candidate_profile,
        "resume_extraction_failed": extraction_failed,
        "execution_trace": trace,
        "errors": errors,
    }


def analyze_job(state: dict) -> dict:
    """LLM structured extraction of requirements from the raw job description."""
    errors = list(state.get("errors", []))
    trace = state.get("execution_trace", [])

    job_description = state.get("job_description", "")
    if not job_description.strip():
        errors.append("Job description is empty.")
        return {
            "job_requirements": JobRequirements(),
            "job_extraction_failed": True,
            "execution_trace": _log(state, "Job description is empty, skipping analysis"),
            "errors": errors,
        }

    try:
        job_requirements = job_analyzer.extract_job_requirements(job_description, state.get("target_role"))
        trace = _log(
            state,
            f"Extracted {len(job_requirements.required_skills)} required and "
            f"{len(job_requirements.preferred_skills)} preferred job skills",
        )
        extraction_failed = False
    except Exception as exc:
        errors.append(f"Job description analysis failed: {exc}")
        job_requirements = JobRequirements()
        trace = _log(state, f"Job description analysis failed, continuing with empty requirements: {exc}")
        extraction_failed = True

    return {
        "job_requirements": job_requirements,
        "job_extraction_failed": extraction_failed,
        "execution_trace": trace,
        "errors": errors,
    }


def match_skills_node(state: dict) -> dict:
    """Deterministic exact/substring skill matching - see services/skill_matcher.py."""
    candidate: CandidateProfile = state.get("candidate_profile", CandidateProfile())
    job: JobRequirements = state.get("job_requirements", JobRequirements())

    matched_required, missing_required = match_skills(candidate.skills, job.required_skills)
    matched_preferred, missing_preferred = match_skills(candidate.skills, job.preferred_skills)

    trace = _log(
        state,
        f"Matched {len(matched_required)}/{len(job.required_skills)} required skills, "
        f"{len(matched_preferred)}/{len(job.preferred_skills)} preferred skills",
    )

    return {
        "matched_required": matched_required,
        "missing_required": missing_required,
        "matched_preferred": matched_preferred,
        "missing_preferred": missing_preferred,
        "execution_trace": trace,
    }


def calculate_score_node(state: dict) -> dict:
    """Deterministic weighted score. No LLM call - see services/scoring.py."""
    score_breakdown = scoring.calculate_score(
        state.get("matched_required", []),
        state.get("missing_required", []),
        state.get("matched_preferred", []),
        state.get("missing_preferred", []),
    )
    trace = _log(state, f"Calculated deterministic compatibility score: {score_breakdown.overall_score}%")
    return {"score_breakdown": score_breakdown, "execution_trace": trace}


def decision_node(state: dict) -> dict:
    """Determine the decision bucket + route deterministically from the score,
    then ask the LLM to explain the decision with evidence-grounded reasoning.

    The score->bucket mapping and the "apply"/"gap_analysis" routing are both
    plain thresholds (see services/scoring.decision_bucket) - the LLM never
    influences which branch the graph takes.
    """
    score = state["score_breakdown"]
    candidate: CandidateProfile = state.get("candidate_profile", CandidateProfile())
    job: JobRequirements = state.get("job_requirements", JobRequirements())

    decision_bucket = scoring.decision_bucket(score.overall_score)
    route = "gap_analysis" if decision_bucket == "LOW_MATCH" else "apply"

    errors = list(state.get("errors", []))

    # If resume and/or job extraction failed (LLM provider down/rate-limited,
    # not a code bug), candidate.skills and/or job.required_skills end up
    # empty - and scoring.calculate_score treats "0 required listed" as "100%
    # satisfied" (correct when a job genuinely lists no requirements, wrong
    # here since nothing was actually analyzed). Left unchecked that produces
    # a confident-looking "100% / STRONG_APPLY" from zero real data - exactly
    # the kind of silent false confidence this app's anti-hallucination
    # design exists to prevent. Skip the LLM explanation entirely in this
    # case (asking it to explain a meaningless number wastes a call against
    # a provider that's likely still failing) and say so plainly instead.
    if state.get("resume_extraction_failed") or state.get("job_extraction_failed"):
        what_failed = []
        if state.get("resume_extraction_failed"):
            what_failed.append("resume")
        if state.get("job_extraction_failed"):
            what_failed.append("job description")
        trace = _log(
            state,
            f"Skipping recommendation explanation - {' and '.join(what_failed)} extraction failed, "
            "score below is not meaningful",
        )
        recommendation = Recommendation(
            decision=decision_bucket,
            confidence="low",
            reasons=[
                f"{' and '.join(what_failed).capitalize()} extraction failed (see Warnings/Errors below) - "
                "this score was computed from incomplete or empty data, not a real analysis. Disregard it "
                "and retry once the underlying issue (commonly an LLM provider rate limit) has cleared."
            ],
            risks=[f"The {decision_bucket} label above does not reflect an actual comparison - treat it as unknown, not as a real result."],
            next_actions=["Retry the analysis. If the error mentions a rate limit, wait for it to clear or switch LLM_PROVIDER in .env."],
        )
        return {
            "decision_bucket": decision_bucket,
            "route": route,
            "recommendation": recommendation,
            "execution_trace": trace,
            "errors": errors,
        }

    trace = _log(state, f"Recommendation generated: {decision_bucket}")

    if score.missing_required:
        trace = trace + [f"Detected {len(score.missing_required)} missing required skill(s): "
                          f"{', '.join(score.missing_required)}"]

    try:
        recommendation = application_generator.generate_recommendation(
            profile=candidate,
            decision_bucket=decision_bucket,
            overall_score=score.overall_score,
            matched_required=score.matched_required,
            missing_required=score.missing_required,
            matched_preferred=score.matched_preferred,
            missing_preferred=score.missing_preferred,
            experience_requirement=job.experience_requirements,
        )
    except Exception as exc:
        errors.append(f"Recommendation generation failed: {exc}")
        # Deterministic fallback so the pipeline can still complete and the UI has something to show.
        reasons = [f"Deterministic score is {score.overall_score}% ({decision_bucket})."]
        if score.missing_required:
            reasons.append(f"Missing required skills: {', '.join(score.missing_required)}.")
        recommendation = Recommendation(
            decision=decision_bucket,
            confidence="low",
            reasons=reasons,
            risks=["LLM explanation unavailable - see errors."],
            next_actions=["Review missing required skills listed above."],
        )
        trace = trace + [f"LLM recommendation explanation failed, using deterministic fallback: {exc}"]

    return {
        "decision_bucket": decision_bucket,
        "route": route,
        "recommendation": recommendation,
        "execution_trace": trace,
        "errors": errors,
    }


def route_after_decision(state: dict) -> str:
    """Conditional-edge function: reads state['route'] set by decision_node."""
    return state.get("route", "apply")


def generate_application(state: dict) -> dict:
    """APPLY branch: resume improvement suggestions + tailored cover letter."""
    candidate: CandidateProfile = state["candidate_profile"]
    job: JobRequirements = state["job_requirements"]
    score = state["score_breakdown"]
    errors = list(state.get("errors", []))

    try:
        improvements = application_generator.generate_resume_improvements(
            candidate, score.missing_required, score.missing_preferred
        )
    except Exception as exc:
        errors.append(f"Resume improvement generation failed: {exc}")
        improvements = []

    try:
        cover_letter = application_generator.generate_cover_letter(candidate, job, score.matched_required)
    except Exception as exc:
        errors.append(f"Cover letter generation failed: {exc}")
        cover_letter = None

    trace = _log(state, "Generated application strategy (resume improvements + cover letter)")
    return {
        "resume_improvements": improvements,
        "cover_letter": cover_letter,
        "gap_analysis": None,
        "execution_trace": trace,
        "errors": errors,
    }


def generate_gap_analysis_node(state: dict) -> dict:
    """LOW_MATCH branch: skip the cover letter, focus on what's missing and why."""
    candidate: CandidateProfile = state["candidate_profile"]
    score = state["score_breakdown"]
    errors = list(state.get("errors", []))

    try:
        gap_text = application_generator.generate_gap_analysis(
            candidate, score.overall_score, score.missing_required, score.missing_preferred
        )
    except Exception as exc:
        errors.append(f"Gap analysis generation failed: {exc}")
        gap_text = None

    try:
        improvements = application_generator.generate_resume_improvements(
            candidate, score.missing_required, score.missing_preferred
        )
    except Exception as exc:
        errors.append(f"Resume improvement generation failed: {exc}")
        improvements = []

    trace = _log(state, "Generated skill gap analysis")
    return {
        "gap_analysis": gap_text,
        "resume_improvements": improvements,
        "cover_letter": None,
        "execution_trace": trace,
        "errors": errors,
    }


def generate_interview_prep(state: dict) -> dict:
    """Final node on both branches: interview questions grounded in matched/missing skills."""
    job: JobRequirements = state["job_requirements"]
    score = state["score_breakdown"]
    errors = list(state.get("errors", []))

    try:
        questions = application_generator.generate_interview_questions(
            job, score.matched_required, score.missing_required
        )
        trace = _log(state, "Generated interview preparation questions")
    except Exception as exc:
        errors.append(f"Interview question generation failed: {exc}")
        questions = []
        # Previously this logged the same success-sounding line regardless of
        # outcome - the trace showed "Generated interview preparation
        # questions" even when the call failed and interview_questions ended
        # up empty (seen live: rate-limited, silently produced nothing, but
        # the trace said it worked). Every other node distinguishes success
        # from failure in its trace line; this one should too.
        trace = _log(state, f"Interview question generation failed, continuing with no questions: {exc}")

    return {"interview_questions": questions, "execution_trace": trace, "errors": errors}
