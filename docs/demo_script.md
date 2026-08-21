# Demo Script (~5 minutes)

## Setup before the room

- Backend running: `python run.py`
- Frontend running: `streamlit run frontend/streamlit_app.py`
- `.env` has a valid `GROQ_API_KEY`
- Have `data/sample_job_description.txt` open, and a real resume PDF ready to upload
- Browser tab open to the Streamlit app, zoomed so text is readable

## Script

**0:00 - 0:30 | Frame the problem**
"Applying to a job means: read the JD, compare it to your resume, find what's missing, decide if it's worth applying, then write a cover letter and prep for the interview. That's a repetitive multi-step workflow - so I built it as an agent, not a chatbot."

**0:30 - 1:00 | Show the input**
Click **"Load sample resume + JD"** in the sidebar (or upload a real resume PDF and paste a real job description). Mention the optional target-role field. Click **Run Agent Analysis**.

**1:00 - 1:30 | While it runs, narrate the pipeline**
"This isn't one LLM call. It's a LangGraph workflow: parse the resume, analyze the job, match skills deterministically, calculate a score with a formula - not a guess - then the LLM explains the recommendation and generates a cover letter or a gap analysis depending on which branch the score routes it to."

**1:30 - 2:30 | Walk the output top to bottom**
- Compatibility score + recommendation label - "this score is computed, not guessed."
- Strong matches / missing skills - point out a required skill that's missing.
- Score breakdown - required vs preferred weighting (80/20).
- "Why this decision?" - read one reason and one risk aloud, especially if a required-skill gap is flagged despite a decent score.

**2:30 - 3:15 | Generated content**
- Resume improvements - point out one that says "Verify before adding" and explain why (anti-hallucination).
- Cover letter (or gap analysis if score was low) - note the greeting/signature (name, contact, company) were filled in automatically from the parsed resume/job posting, not typed by hand.
- Interview questions - point out the categories (technical / gap_related / behavioral).

**3:15 - 3:45 | Execution trace**
Open the "Agent Execution Trace" expander. "This is the safe, visible log of what the agent actually did - not hidden chain-of-thought."

**3:45 - 4:30 | Failure handling (optional, if time)**
Briefly mention (don't necessarily demo live): if the LLM call fails, the node falls back to a deterministic message and the pipeline still completes - show `errors` field if one triggered naturally.

**4:30 - 5:00 | Close**
"Scoring is deterministic and testable - here's the test file." (Optionally flash `tests/test_scoring.py`.) "The LLM is only used where language understanding is genuinely needed: extraction and explanation, never arithmetic."

## If something goes wrong live

- **LLM timeout/error**: point at the `errors` panel in the UI - "this is exactly the graceful degradation I built in, the pipeline still returns a deterministic score even if generation fails."
- **Backend not running**: Streamlit shows a clear "could not reach backend" message, not a stack trace - good recovery talking point.
- **Rate limit on the active provider**: switch `LLM_PROVIDER` in `.env` to the other configured provider (Groq ↔ Gemini) and restart the backend - a one-line, documented recovery, not a code change.
