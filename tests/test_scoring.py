from app.services.scoring import calculate_score, decision_bucket


def test_required_skill_score_matches_example_in_spec():
    # 3/4 required matched = 75%, no preferred skills listed = 100%
    # overall = 75*0.8 + 100*0.2 = 80
    score = calculate_score(
        matched_required=["Python", "FastAPI", "RAG"],
        missing_required=["Docker"],
        matched_preferred=[],
        missing_preferred=[],
    )
    assert score.required_skill_score == 75
    assert score.preferred_skill_score == 100
    assert score.overall_score == 80


def test_weighting_required_dominates_preferred():
    # required fully missing, preferred fully matched -> overall should still be low
    score = calculate_score(
        matched_required=[],
        missing_required=["Python", "SQL"],
        matched_preferred=["Docker"],
        missing_preferred=[],
    )
    assert score.required_skill_score == 0
    assert score.preferred_skill_score == 100
    assert score.overall_score == 20  # 0*0.8 + 100*0.2


def test_no_requirements_at_all_scores_full():
    score = calculate_score([], [], [], [])
    assert score.overall_score == 100


def test_decision_bucket_thresholds():
    assert decision_bucket(85) == "STRONG_APPLY"
    assert decision_bucket(80) == "STRONG_APPLY"
    assert decision_bucket(79) == "APPLY_REVIEW_GAPS"
    assert decision_bucket(65) == "APPLY_REVIEW_GAPS"
    assert decision_bucket(64) == "CONSIDER"
    assert decision_bucket(50) == "CONSIDER"
    assert decision_bucket(49) == "LOW_MATCH"
    assert decision_bucket(0) == "LOW_MATCH"
