# Presentation Structure (10-15 minutes)

## 1. Problem (1 min)
Job applications require a repetitive manual workflow: read JD → compare to resume → find gaps → decide → tailor resume → write cover letter → prep interview. Students repeat this dozens of times.

## 2. Why this problem (1 min)
It's a real, personally-felt pain point with a clean input/output shape (resume + JD → decision + artifacts), which makes it a good fit for demonstrating an agentic pipeline in 24 hours - not too narrow (single API call), not too broad (open-ended automation).

## 3. Existing approaches / alternatives considered and rejected (1-2 min)
- **Manually doing it** - slow, inconsistent, the actual annoyance this project fixes.
- **Generic "paste your resume into ChatGPT"** - a single prompt lets the model invent a match percentage, no reproducibility, high hallucination risk, no structured state to inspect or test. Rejected: not an agent, just a chat reply.
- **Multi-agent framework (CrewAI/AutoGen)** - considered, rejected. The task is a linear pipeline with exactly one branch point (score threshold); multiple negotiating agents would add coordination overhead solving a problem that doesn't exist here. A single LangGraph state machine models it fully - see interview_questions.md.
- **Semantic/embedding-based skill matching** - considered, rejected for scope. A local-embedding retrieval pass would catch worded-differently synonyms ("SQL databases" ~ "PostgreSQL") but adds a real dependency (torch) and real fragility for a recall improvement the assignment doesn't ask for. Exact/substring matching is fast, deterministic, and defensible live.
- **Full application-automation (LinkedIn auto-apply bots)** - out of scope, ethically/practically risky, and not what this assignment asks for (decision support, not action-taking on the user's behalf).

## 4. Our approach (1 min)
An agent with explicit state and conditional workflow: deterministic scoring for anything that's arithmetic/matching, LLM only for language understanding and generation, with anti-hallucination guardrails baked into every prompt.

## 5. Architecture (2 min)
Walk `docs/architecture.md`'s diagram: Streamlit → FastAPI → LangGraph → services → schemas. Emphasize the deterministic/LLM file-level split.

## 6. Agent workflow (2 min)
Walk the 8 nodes and the one conditional branch point (`decision` → apply vs gap_analysis, converging at interview prep). Show `app/agents/graph.py` - the whole graph definition is ~20 lines, readable end to end.

## 7. Tool usage (1-2 min)
List the "tools": PDF parser, skill matcher, deterministic scorer, and 3 distinct LLM-backed generators. Emphasize each is a separately-callable, separately-testable function - not one giant prompt. That's the multi-tool, reasoning-trail bar Option B asks for, exercised inside an Option C build.

## 8. Deterministic vs LLM responsibilities (1-2 min)
Show the README table. Key line: "the LLM never invents the score - it only explains a number that was already computed in code."

## 9. Live demo (5 min)
Follow `docs/demo_script.md`.

## 10. Failure cases (1 min)
- Empty/corrupt PDF → clear 400 error, not a stack trace.
- Missing API key → clear 400 error naming the missing env var.
- LLM call fails mid-graph → node catches the exception, logs to `errors`, falls back to a deterministic message, pipeline still completes (doesn't crash the whole request).
- Malformed LLM output → `with_structured_output` handles schema validation; a retry/failure surfaces as the same graceful fallback path.
- Both extraction calls fail (e.g. provider rate-limited) → the pipeline doesn't let the scoring formula's "no requirements listed = 100% satisfied" rule quietly report a false "Strong Apply" from zero real data; it flags the run as untrustworthy instead. Real bug, found live - see README "Bugs I actually hit".

## 11. Limitations (1 min)
String-normalization skill matching (not semantic) - a deliberate trade-off, not an oversight; no persistence; quality bounded by resume/JD content; structured-output reliability depends on the underlying model; single active LLM provider, no automatic fallback if it goes down mid-demo.

## 12. Future improvements (1 min)
Job board URL ingestion, application tracking (would need a DB), approved browser automation, learning-resource recommendations, historical analytics.
