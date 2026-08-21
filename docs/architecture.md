# Architecture

## Layers

```
frontend/streamlit_app.py    <- thin HTTP client, no business logic
        |
        v  HTTP (multipart form: resume file + job_description + target_role)
app/api/routes.py            <- FastAPI, validation, wires request into AgentState
        |
        v  compiled_graph.invoke(initial_state)
app/agents/graph.py          <- LangGraph node/edge wiring, conditional routing
app/agents/nodes.py          <- thin node functions, call services, update trace/errors
app/agents/state.py          <- AgentState TypedDict (single source of truth per run)
app/agents/prompts.py        <- every LLM prompt template, anti-hallucination wording
        |
        v
app/services/*.py            <- actual work: parsing, matching, scoring, LLM calls
app/schemas/*.py              <- Pydantic contracts (resume, job, analysis, API)
app/core/config.py            <- env-driven settings (provider, model, keys)
```

## Why this split

- **routes.py has no business logic.** It validates the HTTP request, builds the initial state dict, invokes the graph, and maps the result to a response model. If the transport changed (CLI, different framework), only this file would change.
- **nodes.py has no service logic.** Each node function is ~10-20 lines: call a service, handle its exception, append to the trace. This makes the graph's shape (`graph.py`) easy to read independent of implementation detail.
- **services/ has no LangGraph knowledge.** Every service function takes plain arguments and returns a Pydantic model or primitive - each is independently unit-testable and could be reused outside the agent (e.g. a CLI tool).
- **Deterministic vs LLM is a file-level split, not just a runtime one.** `scoring.py` and `skill_matcher.py` import nothing LLM-related. `profile_extractor.py`, `job_analyzer.py`, `application_generator.py` are the only files that call `llm_client.get_chat_model()`.

## Data flow for one request

1. Streamlit uploads resume bytes + job description text to `POST /analyze`.
2. `routes.py` validates presence/size/type, builds `AgentState` with `resume_bytes`, `job_description`, `target_role`, empty `execution_trace`/`errors`.
3. `compiled_graph.invoke(state)` runs the 8 nodes described in the README, each node returning a partial-state dict that LangGraph merges into the running state.
4. The final state's typed fields are assembled into an `AnalysisResult` and returned as JSON.
5. Streamlit renders every field in the layout the assignment specifies (score, recommendation, matches, gaps, breakdown, reasoning, improvements, cover letter, questions, trace).

## State merging note

`AgentState` fields are not annotated with LangGraph reducers - each node returns full replacement values for the keys it owns (e.g. `execution_trace` is read, appended to, and returned as a new list each time) rather than relying on automatic list concatenation. This keeps the merge behavior obvious: "whatever a node returns for a key is now the value of that key."
