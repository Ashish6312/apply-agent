# ApplyAgent

An agent that reads a resume and a job posting, tells you whether it's actually worth applying, and if so, writes you a cover letter and interview prep for it.

I built this for a 24-hour take-home (Option C: pick a real annoyance and fix it agent-style). The annoyance is one I've done by hand more times than I'd like: read the JD, scroll back to my resume, mentally tally what matches, decide if I'm wasting my time, then write a cover letter anyway. It's mechanical enough to automate and just fuzzy enough that a single ChatGPT prompt gets it wrong in ways that are hard to catch.

## Why not just paste it into ChatGPT

Because then the model is inventing your match score out of thin air. Ask twice, get two different numbers. There's no way to tell if it actually checked your resume for a skill or just assumed you probably have it because you're a CS student. And you get one flat block of text back instead of something you can inspect.

So instead of one prompt, this is a pipeline with real steps and real state:

1. Pull text out of the resume PDF (plain extraction, no model involved).
2. Ask an LLM to turn that text into structured fields - skills, projects, experience.
3. Ask an LLM to do the same for the job posting - required skills, preferred skills, responsibilities.
4. Match the two skill lists against each other with actual code, not a vibe.
5. Compute a score with a formula.
6. Route to either "write me a cover letter" or "explain why this isn't a great fit," depending on the score.
7. Generate interview questions either way.

Every step logs what it did, so the UI shows you an actual trace of the run instead of a black box. The score is never something the model guesses - it's arithmetic, computed before the LLM even sees it. The LLM's job is explaining the number, not making it up.

## Architecture

```
                        ┌─────────────────┐
   resume.pdf  ───────► │  FastAPI /analyze │ ◄─────── job_description (text)
                        └─────────┬────────┘
                                  │
                                  ▼
                        ┌──────────────────┐
                        │  LangGraph Agent  │
                        └──────────────────┘
                                  │
   ┌──────────────────────────────────────────────────────────┐
   │  parse_resume → analyze_job → match_skills →              │
   │  calculate_score → decision ─┬─► generate_application ─┐  │
   │                               └─► generate_gap_analysis─┤  │
   │                                                          ▼  │
   │                                       generate_interview_prep│
   └──────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                        AnalysisResult (Pydantic)
                                  │
                                  ▼
                        Streamlit frontend
```

FastAPI does the HTTP layer, LangGraph owns the node/edge wiring, everything that actually does work lives under `app/services/`. Streamlit is a thin client on top - it doesn't contain any logic of its own, it just renders whatever `/analyze` hands back.

### What each node does

| Node | Job | Deterministic or LLM |
|---|---|---|
| `parse_resume` | PDF → text, then text → structured `CandidateProfile` | both |
| `analyze_job` | Job posting text → structured `JobRequirements` | LLM |
| `match_skills` | Compares skill lists, exact/substring | deterministic |
| `calculate_score` | Weighted score from the match results | deterministic |
| `decision` | Score → bucket, bucket → branch, then explain it | mostly deterministic, LLM writes the explanation |
| `generate_application` | Resume tweaks + cover letter (the "apply" branch) | LLM |
| `generate_gap_analysis` | Honest "here's what's missing" instead of a cover letter | LLM |
| `generate_interview_prep` | Interview questions, runs either branch | LLM |

### The services

- `resume_parser.py` - PyMuPDF, pulls text out of the PDF. No model, no ambiguity.
- `profile_extractor.py` / `job_analyzer.py` - the two LLM calls that turn raw text into structured data. Kept in their own files, separate from the parser, so it's obvious at a glance which files touch an LLM and which don't.
- `skill_matcher.py` - exact/substring set comparison. Deterministic, no LLM.
- `scoring.py` - pure functions, no I/O, computes the score and the decision threshold.
- `application_generator.py` - the LLM calls for the recommendation text, cover letter, gap analysis, interview questions.
- `llm_client.py` - one factory function that reads the provider/model from `.env`. Nothing else in the codebase hardcodes a model name.

## Scoring

```
required_skill_score  = matched_required  / total_required  * 100
preferred_skill_score = matched_preferred / total_preferred * 100
overall_score = required_skill_score * 0.8 + preferred_skill_score * 0.2
```

Required skills count for 80% of the score because missing a must-have is a worse signal than missing a nice-to-have. That 80/20 split is a constant at the top of `scoring.py` if you want to argue with it.

| Score | Decision |
|---|---|
| 80-100 | STRONG_APPLY |
| 65-79 | APPLY_REVIEW_GAPS |
| 50-64 | CONSIDER |
| 0-49 | LOW_MATCH |

One thing I made sure of: a high score doesn't bury a real gap. If a required skill has zero evidence in the resume, the recommendation calls it out as a risk no matter how good the overall number looks.

## Guarding against hallucination

- Extraction prompts are told to report only what's literally on the page - nothing inferred.
- The recommendation prompt has to say "insufficient evidence" instead of assuming a skill exists.
- Resume suggestions that would need info not already present have to end with "Verify before adding."
- The decision bucket gets overwritten with the deterministic value right after the LLM call returns, even if the model tried to change it. The LLM explains the decision, it doesn't make it.
- If the resume or job-description extraction itself fails (LLM provider down/rate-limited), the pipeline doesn't let a leftover "no skills listed = 100% satisfied" arithmetic rule quietly report a confident-looking score from zero real data - it flags the run as untrustworthy instead. See "Bugs I actually hit" below, this was a real one.

## Setup (Windows)

```powershell
cd apply-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Environment variables

```
LLM_PROVIDER=gemini
MODEL_NAME=gemini-3.6-flash
GROQ_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
LLM_TIMEOUT_SECONDS=30
LOG_LEVEL=INFO
```

Swap to Groq by setting `LLM_PROVIDER=groq` and `MODEL_NAME=openai/gpt-oss-20b` - no code changes, `llm_client.py` reads both branches from the same `.env`. Running on Gemini right now because Groq's free-tier daily token quota (200k TPD) got exhausted mid-testing; Gemini's quota is separate and untouched. Both model names go stale over time (Groq and Google both retire/rename models) - if either 404s, check the provider's live model list before assuming something's broken.

## Running it

```powershell
python run.py                              # backend, http://127.0.0.1:8000/docs
streamlit run frontend/streamlit_app.py    # frontend, separate terminal
```

## Deploying

For a live URL (not required by the assignment - a local live demo satisfies it - but handy to have): `frontend/streamlit_app.py` can also start the backend itself, in a background thread, so a single [Streamlit Community Cloud](https://streamlit.io/cloud) app is the whole system. Push this repo to GitHub, point a new app at `frontend/streamlit_app.py` (forward slashes, even from a Windows path box), and paste your `.env` values into the app's Secrets panel in TOML form - see `.streamlit/secrets.toml.example` for the shape. First load takes ~20-30s while the backend cold-starts in-process; after that it's instant.

If `python run.py` is already running locally when you also launch Streamlit, the self-start attempt just fails quietly (port already taken) and the app uses that real backend instead - no conflict either way.

## Testing

```powershell
pytest -q
```

Covers PDF parsing, skill matching, scoring, decision thresholds, and API validation. I didn't mock the LLM calls - that would need a fake provider - so those get exercised live instead, via the demo.

## A real run

Sample data lives in `data/` - a generated resume against a backend-intern posting. One real run against Groq: score 67%, 4 of 5 required skills matched, decision `APPLY_REVIEW_GAPS`, a cover letter that actually references the matched project, interview questions that probe the gap. Full pipeline, resume upload to final output, in about 18 seconds. Click "Load sample resume + JD" in the sidebar to run it yourself in one click.

## Bugs I actually hit (and what they taught me)

Not hypotheticals - each of these showed up in a real run and got fixed after seeing the actual failure, not guessed at in advance:

- **A "successful" run reported 100% / STRONG_APPLY from zero real data.** When both the resume and job-description LLM calls failed (a Groq quota exhaustion, mid-testing), `candidate.skills` and `job.required_skills` both ended up empty - and the scoring formula's "no requirements listed = 100% satisfied" rule (correct when a job genuinely lists none) fired anyway. A confidently green "Strong Apply" badge from nothing actually being analyzed is exactly the failure mode this app's whole design is supposed to prevent. Fixed by tracking *why* each field is empty (`resume_extraction_failed`/`job_extraction_failed` in `AgentState`) and short-circuiting to an explicit low-confidence "this score isn't real, retry" result instead of asking the LLM to explain a meaningless number.
- **A slow-but-alive backend crashed the whole page.** The frontend only caught `requests.exceptions.ConnectionError`. `Timeout` is a sibling exception, not a subclass - a request that was genuinely still running server-side (rate-limit retries piling up) crashed the entire Streamlit script with a raw traceback instead of a clean message.
- **A cover letter shipped with a blank body.** The LLM call returned 200 with empty content - no exception, nothing to catch. `invoke_with_retry` now checks for that specifically and retries it like a real failure.

## Limitations

- Skill matching is string-normalization based, not semantic - it will miss a true synonym it wasn't taught to normalize (e.g. "SQL databases" won't match "PostgreSQL" unless the wording lines up). Considered a local-embedding retrieval pass for this and decided against it for the 24h scope: real dependency weight (torch) for a recall improvement the assignment doesn't ask for, and it introduced real fragility (native DLL loading issues) without changing the core decision-support story.
- Nothing persists between runs. Every analysis is stateless.
- Structured extraction leans on the model's function-calling support - a weak model can occasionally choke on it. Handled as a fallback, not a crash, but it's a real dependency.
- Garbage in, garbage out - the cover letter is only as good as what's actually in your resume and the JD.
- A "successful" LLM call can still come back with empty content (seen in testing - no exception, just a blank string). `invoke_with_retry` now treats that as a failure and retries rather than shipping a cover letter with a hole where the body should be, but it's worth knowing this class of failure exists rather than assuming a 200 means real content.
- Single provider active at a time (Groq or Gemini, whichever `LLM_PROVIDER` names) - no automatic fallback between them. If the active provider's quota runs out mid-demo, that's a `.env` edit and a restart, not something the app recovers from on its own - hit this for real (Groq's 200k TPD free-tier quota) and switched to Gemini as a result.

## What I'd build next

Pulling job descriptions straight from a URL instead of copy-paste, tracking applications across multiple runs (needs a database, which this deliberately doesn't have), and tying missing skills to actual learning resources instead of just naming them.

## What I didn't build, on purpose

**A multi-agent setup (CrewAI, etc.)** - this is a linear pipeline with one branch point. A single state graph covers it completely. Multiple agents negotiating with each other would add coordination overhead for a problem I don't have.

**A database** - stateless, single-request tool. In-memory state for the duration of one run is enough.

**Semantic/embedding-based skill matching** - considered, cut. Would trade a real dependency (torch, ~500MB) and genuine platform fragility (native DLL loading issues, hit live during development) for a recall improvement on skill-phrase synonyms the assignment doesn't ask for. Exact/substring matching is fast, deterministic, and defensible in a live demo; the marginal recall gain wasn't worth the weight or the risk for a 24-hour prototype.

**A PDF/document export** - the assignment explicitly doesn't need a separate written report. The UI's cover letter and gap analysis are already copy-paste text, which is the actual use case (pasting into an application form).

**Multiple LLM providers with automatic fallback** - considered, cut. A single configured provider (`LLM_PROVIDER`) with a documented one-line swap to a second (Groq ↔ Gemini) is simpler to reason about and explain live than routing logic between providers - and the assignment's own framing ("any model or API you have access to") points at picking one, not engineering resilience across several.

**Anything that submits an application on your behalf.** Too high-stakes to automate without a human actually reading it first. This tool stops at "here's your cover letter," it doesn't click submit.

**Docker/Kubernetes/Redis/a separate hosted backend.** No background jobs, no multi-service infrastructure. The backend either runs locally alongside the frontend, or gets started by the frontend itself in-process for a single-service Streamlit Cloud deploy (see "Deploying") - either way it's at most two plain processes, never more.

---

There's also a presentation outline, a timed demo script, and a page of interview Q&A prep under `docs/` - mostly notes I wrote for myself before presenting this, not really meant for an outside reader, but they're there if you want the full backstory.
