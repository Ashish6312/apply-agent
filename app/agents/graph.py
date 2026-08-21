"""LangGraph wiring: defines the node graph and conditional routing.

    START -> parse_resume -> analyze_job -> match_skills -> calculate_score
          -> decision --(route)--> generate_application ----\\
                       \\-------> generate_gap_analysis ----> generate_interview_prep -> END

The "decision" node is the only branch point: it deterministically computes
a score-based route ("apply" vs "gap_analysis") and the conditional edge
below just reads that value. Both branches converge on generate_interview_prep
because every candidate benefits from interview prep regardless of how
strong the match is.
"""
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    analyze_job,
    calculate_score_node,
    decision_node,
    generate_application,
    generate_gap_analysis_node,
    generate_interview_prep,
    match_skills_node,
    parse_resume,
    route_after_decision,
)
from app.agents.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("parse_resume", parse_resume)
    graph.add_node("analyze_job", analyze_job)
    graph.add_node("match_skills", match_skills_node)
    graph.add_node("calculate_score", calculate_score_node)
    graph.add_node("decision", decision_node)
    graph.add_node("generate_application", generate_application)
    graph.add_node("generate_gap_analysis", generate_gap_analysis_node)
    graph.add_node("generate_interview_prep", generate_interview_prep)

    graph.add_edge(START, "parse_resume")
    graph.add_edge("parse_resume", "analyze_job")
    graph.add_edge("analyze_job", "match_skills")
    graph.add_edge("match_skills", "calculate_score")
    graph.add_edge("calculate_score", "decision")

    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"apply": "generate_application", "gap_analysis": "generate_gap_analysis"},
    )

    graph.add_edge("generate_application", "generate_interview_prep")
    graph.add_edge("generate_gap_analysis", "generate_interview_prep")
    graph.add_edge("generate_interview_prep", END)

    return graph.compile()


# Compiled once per process and reused across requests - the graph itself is
# stateless (all state lives in the AgentState dict passed to .invoke()).
compiled_graph = build_graph()
