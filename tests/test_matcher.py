from app.services.skill_matcher import match_skills


def test_exact_match_case_insensitive():
    matched, missing = match_skills(["Python", "FastAPI"], ["python", "fastapi"])
    assert matched == ["python", "fastapi"]
    assert missing == []


def test_missing_skill_detected():
    matched, missing = match_skills(["Python", "FastAPI", "RAG"], ["Python", "FastAPI", "RAG", "Docker"])
    assert matched == ["Python", "FastAPI", "RAG"]
    assert missing == ["Docker"]


def test_substring_variant_match():
    # "React.js" in resume should satisfy a job requirement of "React"
    matched, missing = match_skills(["React.js"], ["React"])
    assert matched == ["React"]
    assert missing == []


def test_empty_job_skill_list_returns_no_matches_or_missing():
    matched, missing = match_skills(["Python"], [])
    assert matched == []
    assert missing == []


def test_no_candidate_skills_means_everything_missing():
    matched, missing = match_skills([], ["Python", "SQL"])
    assert matched == []
    assert missing == ["Python", "SQL"]
