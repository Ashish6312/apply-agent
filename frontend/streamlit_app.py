"""ApplyAgent Streamlit UI.

Thin client over the FastAPI backend: it uploads the resume + job
description to POST /analyze and renders the structured response. No
business logic lives here - that keeps the UI swappable/replaceable
without touching the agent.
"""
import os
import sys
from pathlib import Path

import requests
import streamlit as st

# Allow `import app.*` when Streamlit launches this file directly (its sys.path
# only contains frontend/, not the project root).
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.utils.helpers import decision_label  # noqa: E402

DEFAULT_API_URL = os.environ.get("APPLYAGENT_API_URL", "http://127.0.0.1:8000")
ANALYZE_TIMEOUT_SECONDS = 120  # 8 sequential LLM calls per run, comfortable margin on a fast provider
SAMPLE_JD_PATH = ROOT_DIR / "data" / "sample_job_description.txt"
SAMPLE_RESUME_PATH = ROOT_DIR / "data" / "sample_resume.pdf"

DECISION_STYLE = {
    "STRONG_APPLY": {"color": "#16A34A", "bg": "rgba(22,163,74,0.15)", "icon": "✅"},
    "APPLY_REVIEW_GAPS": {"color": "#2563EB", "bg": "rgba(37,99,235,0.15)", "icon": "📝"},
    "CONSIDER": {"color": "#D97706", "bg": "rgba(217,119,6,0.15)", "icon": "🤔"},
    "LOW_MATCH": {"color": "#DC2626", "bg": "rgba(220,38,38,0.15)", "icon": "⛔"},
}

st.set_page_config(page_title="ApplyAgent", page_icon="🎯", layout="wide")

# Streamlit Cloud has no .env file - config is set via st.secrets instead.
# Mirror it into os.environ so app.core.config.Settings (which reads env
# vars / .env, same as locally) sees it the same way either way. Only touch
# st.secrets if a secrets.toml actually exists - merely *accessing* it with
# none present prints a "No secrets found" banner in the app itself, which
# a plain try/except can't suppress since it's not a raised exception.
_secrets_paths = [ROOT_DIR / ".streamlit" / "secrets.toml", Path.home() / ".streamlit" / "secrets.toml"]
if any(p.exists() for p in _secrets_paths):
    try:
        for _key, _value in st.secrets.items():
            os.environ.setdefault(_key, str(_value))
    except Exception:
        pass  # malformed secrets.toml or similar - .env still covers local dev


@st.cache_resource
def _launch_embedded_backend_thread() -> None:
    """Start the FastAPI backend in a background thread inside this same
    process, exactly once. Streamlit Cloud only exposes one port, so there's
    nowhere to deploy a separate backend service alongside it - the backend
    runs in-process on localhost instead, api_url stays http://127.0.0.1:8000
    exactly as it is for local dev. Locally, if `python run.py` is already
    bound to the port (the normal two-terminal workflow), this thread's own
    bind attempt just fails quietly - the real backend already there keeps
    serving and the health check below finds it.
    """
    import threading

    import uvicorn

    from app.main import app as fastapi_app

    def _run() -> None:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")

    threading.Thread(target=_run, daemon=True).start()


def _wait_for_embedded_backend(max_wait_seconds: float = 20) -> None:
    """Poll until the backend answers, or max_wait_seconds elapses - deliberately
    NOT cached, unlike the launcher above. A slow cold start (imports, disk
    contention) can take longer than any fixed window; caching the *wait*
    alongside the *launch* would mean one slow attempt gets permanently
    marked "done" whether or not the backend actually came up, and every
    later rerun (e.g. clicking Analyze) would skip the wait and go straight
    to "could not reach backend" forever. Calling this fresh on every rerun
    costs nothing once the backend is actually up (the first check inside
    the loop succeeds immediately) and keeps giving it more chances if not.
    """
    import time

    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        try:
            requests.get("http://127.0.0.1:8000/health", timeout=0.3)
            return
        except requests.exceptions.RequestException:
            time.sleep(0.2)


if os.environ.get("APPLYAGENT_EMBEDDED_BACKEND", "true").lower() == "true":
    _launch_embedded_backend_thread()
    _wait_for_embedded_backend()

# ---------------------------------------------------------------- styling --
st.markdown(
    """
    <style>
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(90deg, #60A5FA, #2563EB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .hero-sub {
        color: #94A3B8;
        font-size: 1.02rem;
        margin-top: 0.15rem;
        margin-bottom: 1.2rem;
    }
    .chip {
        display: inline-block;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.85rem;
        margin: 0.15rem 0.3rem 0.15rem 0;
        font-weight: 500;
    }
    .chip-ok   { background: rgba(22,163,74,0.15);  color: #16A34A; }
    .chip-req  { background: rgba(220,38,38,0.15);  color: #DC2626; }
    .chip-pref { background: rgba(217,119,6,0.15);  color: #D97706; }
    .decision-badge {
        display: inline-block;
        padding: 0.55rem 1.1rem;
        border-radius: 10px;
        font-size: 1.15rem;
        font-weight: 700;
    }
    .step-line { color: #94A3B8; font-size: 0.92rem; padding: 0.15rem 0; }
    .footer-note { color: #64748B; font-size: 0.82rem; text-align: center; margin-top: 2.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------- state --
st.session_state.setdefault("api_url", DEFAULT_API_URL)
st.session_state.setdefault("result", None)
st.session_state.setdefault("jd_text", "")
st.session_state.setdefault("target_role", "")
st.session_state.setdefault("resume_bytes", None)
st.session_state.setdefault("resume_name", None)

# ------------------------------------------------------------------ sidebar --
with st.sidebar:
    st.markdown("## 🎯 ApplyAgent")
    st.caption("AI agent for job-application decisions")
    st.divider()

    st.session_state["api_url"] = st.text_input("Backend URL", value=st.session_state["api_url"])

    st.divider()
    st.markdown("**Try it instantly**")
    if st.button("📎 Load sample resume + JD", use_container_width=True):
        if SAMPLE_JD_PATH.exists():
            st.session_state["jd_text"] = SAMPLE_JD_PATH.read_text(encoding="utf-8")
        if SAMPLE_RESUME_PATH.exists():
            st.session_state["resume_bytes"] = SAMPLE_RESUME_PATH.read_bytes()
            st.session_state["resume_name"] = SAMPLE_RESUME_PATH.name
        st.session_state["target_role"] = "Backend Engineering Intern"
        st.rerun()

    st.divider()
    st.markdown("**How the agent works**")
    st.markdown(
        """
        <div class="step-line">1. Parse resume (PDF → text)</div>
        <div class="step-line">2. Structure resume → skills/experience (LLM)</div>
        <div class="step-line">3. Structure job posting → requirements (LLM)</div>
        <div class="step-line">4. Match skills (deterministic)</div>
        <div class="step-line">5. Score compatibility (deterministic)</div>
        <div class="step-line">6. Decide + explain (LLM, evidence-grounded)</div>
        <div class="step-line">7. Generate cover letter / gap analysis (LLM)</div>
        <div class="step-line">8. Generate interview prep (LLM)</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Stack: FastAPI · LangGraph · Pydantic · Streamlit · Groq / Gemini")

# -------------------------------------------------------------------- hero --
st.markdown('<div class="hero-title">ApplyAgent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Agentic pipeline that reads a resume and a job posting, '
    "computes a reproducible compatibility score, and generates a tailored application "
    "strategy — with full reasoning visible at every step.</div>",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------- input --
with st.container(border=True):
    st.markdown("#### Input")
    col1, col2 = st.columns([1, 1.3])
    with col1:
        resume_file = st.file_uploader("Resume (PDF)", type=["pdf"])
        if resume_file is not None:
            st.session_state["resume_bytes"] = resume_file.getvalue()
            st.session_state["resume_name"] = resume_file.name
        if st.session_state["resume_bytes"]:
            st.caption(f"📄 Using: **{st.session_state['resume_name']}**")

        target_role = st.text_input(
            "Target role / preferences (optional)",
            value=st.session_state["target_role"],
            placeholder="e.g. Backend Intern",
        )
    with col2:
        job_description = st.text_area(
            "Job Description",
            value=st.session_state["jd_text"],
            height=232,
            placeholder="Paste the full job posting here...",
        )

    analyze_clicked = st.button("🚀 Run Agent Analysis", type="primary", use_container_width=True)

# ------------------------------------------------------------------- call ---
if analyze_clicked:
    if not st.session_state["resume_bytes"]:
        st.error("Please upload a resume PDF (or load the sample from the sidebar).")
    elif not job_description.strip():
        st.error("Please paste a job description.")
    else:
        with st.status("Running agent pipeline...", expanded=True) as status:
            status.write("Sending resume + job description to the LangGraph agent...")
            try:
                response = requests.post(
                    f"{st.session_state['api_url']}/analyze",
                    files={
                        "resume": (
                            st.session_state["resume_name"] or "resume.pdf",
                            st.session_state["resume_bytes"],
                            "application/pdf",
                        )
                    },
                    data={"job_description": job_description, "target_role": target_role or ""},
                    timeout=ANALYZE_TIMEOUT_SECONDS,
                )
            except requests.exceptions.ConnectionError:
                status.update(label="Could not reach backend", state="error")
                st.error(
                    f"Could not reach the backend at {st.session_state['api_url']}. "
                    "Is `python run.py` running?"
                )
                st.stop()
            except requests.exceptions.Timeout:
                # A slow provider (rate-limit retries) can genuinely take longer than
                # the client timeout - that's not a crash, it's the request still
                # running server-side. requests.Timeout is a different exception from
                # ConnectionError, so both need their own handler or a slow-but-alive
                # backend crashes the whole page with a raw traceback.
                status.update(label="Request timed out", state="error")
                st.error(
                    f"The backend didn't respond within {ANALYZE_TIMEOUT_SECONDS}s. It may still be "
                    "working - check its terminal/log. Common cause: an LLM provider rate limit "
                    "forcing several retries in a row. Try again in a few minutes."
                )
                st.stop()

            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                status.update(label="Agent run failed", state="error")
                st.error(f"Analysis failed: {detail}")
                st.stop()

            result = response.json()["result"]
            for line in result["execution_trace"]:
                status.write(f"✔ {line}")
            status.update(label="Agent run complete", state="complete")

        st.session_state["result"] = result

# ------------------------------------------------------------------ output --
result = st.session_state.get("result")

if not result:
    st.info("Upload a resume and job description (or click **Load sample resume + JD** in the sidebar), then run the agent.")
else:
    score = result["score_breakdown"]
    recommendation = result["recommendation"]
    decision = recommendation["decision"]
    style = DECISION_STYLE.get(decision, {"color": "#94A3B8", "bg": "rgba(148,163,184,0.15)", "icon": "•"})

    tab_overview, tab_skills, tab_strategy, tab_interview, tab_trace = st.tabs(
        ["📊 Overview", "🧩 Skills & Score", "📝 Application Strategy", "🎤 Interview Prep", "🔍 Agent Trace"]
    )

    # ---- Overview -----------------------------------------------------
    with tab_overview:
        profile = result["candidate_profile"]
        job = result["job_requirements"]
        subtitle_bits = [b for b in (profile.get("name"), job.get("role"), job.get("company")) if b]
        if subtitle_bits:
            st.caption(" · ".join(subtitle_bits))

        c1, c2, c3 = st.columns([1.1, 1, 1])
        with c1:
            st.markdown(
                f'<span class="decision-badge" style="color:{style["color"]}; background:{style["bg"]};">'
                f'{style["icon"]} {decision_label(decision)}</span>',
                unsafe_allow_html=True,
            )
            st.caption(f"Confidence: **{recommendation['confidence']}**")
        c2.metric("Compatibility Score", f"{score['overall_score']}%")
        c3.metric("Required Skills Matched", f"{len(score['matched_required'])}/{len(score['matched_required']) + len(score['missing_required'])}")

        st.progress(score["overall_score"] / 100)

        st.markdown("##### Why this decision?")
        for reason in recommendation["reasons"]:
            st.markdown(f"- {reason}")

        if recommendation["risks"]:
            st.markdown("##### ⚠️ Risks")
            for risk in recommendation["risks"]:
                st.warning(risk)

        if recommendation["next_actions"]:
            st.markdown("##### Next actions")
            for action in recommendation["next_actions"]:
                st.markdown(f"- {action}")

    # ---- Skills & Score -------------------------------------------------
    with tab_skills:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("**✅ Strong Matches**")
            chips = "".join(f'<span class="chip chip-ok">✓ {s}</span>' for s in score["matched_required"] + score["matched_preferred"])
            st.markdown(chips or "_No matches found._", unsafe_allow_html=True)
        with m2:
            st.markdown("**Gaps**")
            chips = "".join(f'<span class="chip chip-req">✗ {s} (required)</span>' for s in score["missing_required"])
            chips += "".join(f'<span class="chip chip-pref">△ {s} (preferred)</span>' for s in score["missing_preferred"])
            st.markdown(chips or "_No gaps found._", unsafe_allow_html=True)

        st.divider()
        st.markdown("##### Score Breakdown")
        b1, b2 = st.columns(2)
        b1.metric("Required skill score", f"{score['required_skill_score']}%", help="Weighted 80% of overall score")
        b2.metric("Preferred skill score", f"{score['preferred_skill_score']}%", help="Weighted 20% of overall score")
        st.caption("`overall = required_score × 0.8 + preferred_score × 0.2` — computed deterministically, never guessed by the LLM.")

        if result["resume_improvements"]:
            st.divider()
            st.markdown("##### Resume Improvements")
            for suggestion in result["resume_improvements"]:
                st.markdown(f"- {suggestion}")

    # ---- Application Strategy -----------------------------------------
    with tab_strategy:
        profile = result["candidate_profile"]
        job = result["job_requirements"]
        if result.get("cover_letter"):
            company_name = job.get("company")
            source_note = f"your resume and the job posting ({company_name})" if company_name else "your resume"
            st.markdown("##### Generated Cover Letter")
            st.caption(
                f"Ready to copy-paste — name, contact details, and greeting are filled in "
                f"automatically from {source_note}. Click inside the box, **Ctrl+A** then **Ctrl+C** "
                "to copy, or use the download button below."
            )
            st.text_area("Cover letter", result["cover_letter"], height=340, label_visibility="collapsed")
            st.download_button(
                "⬇ Download cover letter (.txt)",
                data=result["cover_letter"],
                file_name=f"cover_letter_{(profile.get('name') or 'candidate').replace(' ', '_').lower()}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        elif result.get("gap_analysis"):
            st.markdown("##### Gap Analysis")
            st.write(result["gap_analysis"])
            st.download_button(
                "⬇ Download gap analysis (.txt)",
                data=result["gap_analysis"],
                file_name="gap_analysis.txt",
                mime="text/plain",
            )
        else:
            st.caption("No application strategy content was generated for this run.")

    # ---- Interview Prep --------------------------------------------------
    with tab_interview:
        questions = result["interview_questions"]
        if not questions:
            st.caption("No interview questions generated.")
        else:
            by_category: dict[str, list[str]] = {}
            for q in questions:
                by_category.setdefault(q["category"], []).append(q["question"])
            for category, qs in by_category.items():
                st.markdown(f"##### {category.replace('_', ' ').title()}")
                for q in qs:
                    st.markdown(f"- {q}")

    # ---- Agent Trace -------------------------------------------------------
    with tab_trace:
        st.markdown("##### Execution Trace")
        st.caption("What the agent actually did at each node — not raw model chain-of-thought.")
        for step in result["execution_trace"]:
            st.markdown(f'<div class="step-line">▸ {step}</div>', unsafe_allow_html=True)

        if result["errors"]:
            st.markdown("##### Warnings / Errors")
            for err in result["errors"]:
                st.warning(err)

        with st.expander("Extracted candidate profile (raw)"):
            st.json(result["candidate_profile"])
        with st.expander("Extracted job requirements (raw)"):
            st.json(result["job_requirements"])

st.markdown(
    '<div class="footer-note">ApplyAgent — FastAPI + LangGraph agent, deterministic scoring, '
    "evidence-grounded LLM reasoning.</div>",
    unsafe_allow_html=True,
)
