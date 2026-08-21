# Interview Questions & Answers

**Why is this an agent, not just a chatbot?**
Because it has explicit typed state (`AgentState`) that accumulates across steps, calls multiple distinct tools/services in sequence, makes a conditional routing decision based on computed evidence (score), and produces a visible execution trace of what it did. A chatbot is one prompt → one response; this is a multi-step pipeline with branching control flow.

**Why LangGraph?**
It gives me an explicit state machine: typed state, named nodes, and conditional edges I can point to and explain line by line. The alternative (chaining LLM calls manually in a function) hides the control flow in imperative code; LangGraph makes the workflow itself an inspectable object (`graph.py`), which is exactly what needs to be demoed and defended in an interview.

**Why not a single LLM prompt?**
A single prompt would have to invent the compatibility score (unreproducible), risk hallucinating skill matches, and couldn't cleanly separate "what's true" from "what's generated." Splitting into deterministic matching/scoring + separate, narrowly-scoped LLM calls makes each part independently correct and testable.

**Why not CrewAI (or another multi-agent framework)?**
This is a linear pipeline with one branch point, not a group of autonomous agents that need to negotiate, delegate, or converse with each other. A single state graph fully models it. Multi-agent frameworks add coordination overhead (agent-to-agent messaging, role prompts) that would solve a problem I don't have here - CrewAI is closer to what you'd DAG-orchestrate when you actually have specialized agents debating; I have specialized functions.

**Why deterministic scoring?**
Arithmetic and set comparison must be reproducible and testable - two runs on the same resume/JD should give the same score. An LLM asked "what's the match percentage" will vary run to run and can't be unit tested the way `calculate_score()` can (see `tests/test_scoring.py`).

**How do you prevent hallucinations?**
Three layers: (1) extraction prompts instruct the model to only report what's literally in the text; (2) the recommendation prompt requires "Insufficient evidence" phrasing instead of assuming a skill exists, and treats a missing required skill as a real risk regardless of score; (3) resume-improvement suggestions that would need information not present in the resume must end with "Verify before adding." The score and decision bucket themselves are never LLM-generated at all - the LLM's `decision` field is even forcibly overwritten with the deterministic value after the call, as a hard guardrail.

**What happens if the resume is missing information?**
The extraction returns empty lists/nulls for missing fields rather than inventing content. Downstream, missing required skills show up as explicit gaps in the score breakdown and recommendation - the system treats "no evidence" as "not matched," never as "probably has it."

**What happens if the LLM API fails (timeout, malformed output, missing key)?**
Missing API key is caught before the graph even runs (`400` with a clear message). Mid-graph LLM failures are caught per-node - each node wraps its LLM call in try/except, logs a message to `errors`, and falls back to a deterministic/minimal result so the rest of the pipeline still completes instead of crashing the whole request. `with_structured_output` handles schema validation of the LLM's response, so malformed output raises a catchable exception rather than silently returning bad data.

**Why not semantic/embedding-based skill matching?**
Considered it - a local embedding model retrieving "SQL databases" ~ "PostgreSQL" by cosine similarity would catch real synonyms exact matching misses. Cut it for scope: it's a real dependency (torch) for a recall improvement the assignment doesn't ask for, and I hit genuine platform fragility with it (native DLL loading issues) during a spike. Exact/substring matching is fast, deterministic, fully covered by unit tests, and defensible live - the better trade for a 24-hour prototype.

**Why no multi-agent architecture?**
See "why not CrewAI" - the task decomposes cleanly into a linear pipeline with one decision point, which a single graph models completely. Multiple agents would need a reason to exist independently (different goals, different context, negotiation) and none of that applies here.

**How would you scale this?**
Move state out of memory into a job store (e.g. Redis or a DB) if I needed async/queued processing; add caching on the job-description extraction (same JD analyzed by many candidates); consider batching or a cheaper model for the extraction steps and reserving the strongest model for the recommendation/generation steps; add rate limiting and per-user usage tracking if it became multi-tenant.

**How would you evaluate the system?**
Deterministic parts (scoring, matching) are covered by unit tests with known inputs/outputs. For the LLM parts, I'd build a small labeled set of (resume, JD, expected key skills) pairs and check extraction recall/precision against it, plus a human rubric for cover-letter/gap-analysis quality (relevance, no hallucinated facts, actionable-ness) scored by a few reviewers.

**What metrics would you use?**
Skill-extraction precision/recall against a labeled set; score stability (same input → same score, trivially 100% by construction); hallucination rate (spot-checking generated text against source resume); node failure rate (how often the LLM fallback path triggers); end-to-end latency per analysis.

**What would you build next?**
Application tracking across multiple analyses (needs a lightweight DB), job-description ingestion from a URL, and learning-resource suggestions tied to specific missing skills.

**What was your biggest 24-hour trade-off?**
Deciding when to stop adding capability and just ship what the assignment actually asks for. I spiked semantic skill matching, multi-provider fallback, and a couple of other extras mid-build - all technically working - and then cut them back out once I looked at the brief again: none of it changes the core "is this an agent that reasons over real tools and explains itself" story, and each one added a dependency or a failure surface the simpler version doesn't have. The build that's left is the one I can defend line by line in the room.

**Why did you separate `resume_parser.py` from `profile_extractor.py` instead of one "resume service"?**
So the deterministic/LLM boundary is visible in the file layout, not just in comments - anyone reading the services folder can tell at a glance which files are pure logic and which call an LLM, without reading the function bodies.

**Why is `execution_trace` shown but not raw chain-of-thought?**
The assignment asks for visible reasoning/strategy without exposing an LLM's private chain-of-thought (which many providers also disallow surfacing). The trace is a curated, safe log of *what the system did* ("Matched 6/8 required skills") - factual and auditable, not the model's internal token-by-token reasoning.

**What's the single most important design decision here?**
Keeping the score and the decision bucket 100% deterministic and letting the LLM only explain/generate around that fixed point. It's what makes the whole system testable, reproducible, and defensible instead of "an LLM said so."

**Tell me about a real bug you hit while building this.**
Mid-testing, my LLM provider's daily quota ran out, so both extraction calls (resume, job description) failed - and the run still came back showing "100% - Strong Apply." The scoring formula has a rule that "0 required skills listed = 100% satisfied," which is correct when a job genuinely lists none, but here the zero was from a total extraction failure, not an empty job posting. A confidently green result from analyzing nothing is a worse failure than an error message - it's the exact silent-false-confidence problem this whole app is designed to avoid, just showing up in a code path I hadn't stress-tested. Fixed it by explicitly tracking *why* the data is empty (`resume_extraction_failed`/`job_extraction_failed` flags in state) and short-circuiting to an honest "this score isn't real, retry" result instead of asking the LLM to rationalize a meaningless number.

**How do you find bugs like that if you're not actively trying to break things?**
I don't go looking for edge cases in the abstract - I run the real thing against real, occasionally-uncooperative infrastructure (a rate-limited provider, a slow network) and watch what the *system* does when the *inputs* to it fail, not just when my own code throws. Two of the bugs in this build came from that: the false-confidence score above, and a frontend that crashed on a slow-but-alive request because it only caught one of two relevant timeout/connection exception types. Neither shows up in a unit test with mocked LLM calls - they only show up when something upstream is actually behaving badly.
