"""All LLM prompt templates in one place, so the exact wording driving each
LLM call (and the anti-hallucination guardrails) is easy to find and review.

Every prompt that touches candidate facts repeats the same rule: ground
claims strictly in the provided text, never invent details. This is
deliberate repetition, not copy-paste laziness - each prompt is used in
isolation by a different LLM call with no shared context, so the guardrail
has to be restated every time.
"""

RESUME_EXTRACTION_PROMPT = """You are extracting structured information from a resume.

Rules:
- The "skills" field should be SHORT SKILL/TOOL/TECHNOLOGY NAMES (1-4 words
  each), gathered from anywhere in the resume: an explicit skills section,
  AND tools/technologies explicitly named inside experience or project
  descriptions (e.g. "built REST APIs in Django" -> include "Django").
- Only report a skill if it is explicitly named in the text - do not infer a
  skill just because it sounds related to something mentioned, and do not
  invent companies, job titles, dates, or achievements.
- The contact/header line at the top of the resume (name, email, phone,
  location, links, usually separated by "|", "-", or commas) almost always
  contains the name, email, phone, and location fields - read it carefully
  and split it out field by field rather than only grabbing the email.
  Example: "Jane Doe | jane@mail.com | +1 555-0100 | Austin, TX" ->
  name="Jane Doe", email="jane@mail.com", phone="+1 555-0100", location="Austin, TX".
- Extract each field exactly as written - never invent or guess a value that
  isn't present. If a field genuinely isn't anywhere in the resume, leave it
  empty/null - don't leave it null just because it takes extra effort to find.

Resume text:
---
{resume_text}
---
"""

JOB_EXTRACTION_PROMPT = """You are extracting structured requirements from a job description.

Rules:
- required_skills and preferred_skills must be SHORT SKILL/TOOL/TECHNOLOGY NAMES
  only (e.g. "Python", "FastAPI", "SQL", "Docker"), 1-4 words each - never full
  sentences copied from the posting.
- Separate skills that are stated as REQUIRED/must-have from those stated as
  PREFERRED/nice-to-have/bonus. If the posting doesn't distinguish, use your
  best judgment based on the language used (e.g. "must have" vs "a plus").
- Do NOT put eligibility criteria (degree/education status, work authorization,
  location, GPA) into required_skills or preferred_skills - those are not
  skills. Ignore them entirely unless they belong in experience_requirements.
- Extract the hiring company/organization name if it is stated anywhere in the
  posting - check the title line first (e.g. "Backend Intern - Acme Analytics"
  or "Acme Analytics is hiring a Backend Intern" both mean company="Acme
  Analytics"), then the body (e.g. "About Acme Analytics", "join the team at
  Acme"). Leave null only if genuinely not mentioned anywhere - never guess.
- List responsibilities as short, distinct bullet points.
- Target role hint from the user (may be empty, use only as context): {target_role_hint}

Job description:
---
{job_description}
---
"""

RECOMMENDATION_PROMPT = """You are explaining a job-application recommendation to a candidate.

The compatibility score and decision category below were already computed
deterministically - do not change them or invent a different score. Your job
is only to explain WHY, grounded strictly in the evidence provided.

Critical rule: if a listed missing required skill has no evidence in the
candidate's resume, treat that as a real risk even if the overall score is
high - do not paper over it. If evidence for a claim is unclear, say
"Insufficient evidence" rather than assuming the candidate has a skill.

Decision category (deterministic, already decided): {decision_bucket}
Overall compatibility score (deterministic, already decided): {overall_score}%

Evidence:
- Candidate skills found in resume: {candidate_skills}
- Required skills matched: {matched_required}
- Required skills MISSING (no resume evidence): {missing_required}
- Preferred skills matched: {matched_preferred}
- Preferred skills missing: {missing_preferred}
- Candidate years of experience (if known): {years_of_experience}
- Job experience requirement: {experience_requirement}

Produce the `decision` field exactly as given above ({decision_bucket}). Produce
confidence, reasons, risks, and next_actions based on the evidence.
"""

RESUME_IMPROVEMENT_PROMPT = """You are suggesting resume improvements for this specific job application.

Critical rule: NEVER invent companies, job titles, years of experience,
certifications, technologies, or metrics that are not already in the
resume. If a suggestion would require information not present in the
resume evidence below, the suggestion text MUST end with the literal
phrase "Verify before adding."

Resume evidence (skills/experience/projects actually found):
{candidate_summary}

Missing required skills for this job: {missing_required}
Missing preferred skills for this job: {missing_preferred}

Suggest 3-6 concrete, actionable improvements (wording changes, sections to
add emphasis to, skills to highlight if there is evidence for them, etc.).

Respond with JSON only, in exactly this shape: {{"improvements": ["suggestion 1", "suggestion 2", ...]}}.
The key must be named "improvements".
"""

COVER_LETTER_PROMPT = """Write the BODY of a tailored, professional cover letter (3 short paragraphs,
220-320 words total) for this candidate applying to this role at {company}.

Rules:
- Only reference skills, projects, and experience that appear in the candidate evidence below.
- Do not invent achievements, metrics, dates, or experience.
- Paragraph 1: state the role being applied for and one genuine, specific hook connecting the
  candidate's background to it (a matched skill or project, not generic enthusiasm).
- Paragraph 2: back it up with 2-3 concrete matched skills/projects/responsibilities from the
  evidence below - specifics, not adjectives.
- Paragraph 3: brief, confident close (no restating the whole letter).
- Professional, confident, no purple prose, no cliches ("team player", "hard worker").
- Do NOT include a date, salutation ("Dear..."), sign-off ("Sincerely,..."), or the candidate's
  name/contact details - those are added separately. Return ONLY the body paragraphs.

Role: {role}
Company: {company}
Candidate evidence:
{candidate_summary}

Matched required skills: {matched_required}
Key job responsibilities: {responsibilities}

Return only the body paragraphs, separated by a blank line.
"""

GAP_ANALYSIS_PROMPT = """This candidate's compatibility score for this role is low ({overall_score}%).
Write a short, honest gap analysis (120-200 words) instead of a cover letter.

Explain, grounded in the evidence below:
- Why the match is currently weak (reference the specific missing required skills).
- What the candidate would realistically need to build/learn to be competitive.
- Whether applying anyway could still make sense (e.g. if only 1 skill is missing vs many).

Do not invent resume content. Be constructive, not discouraging.

Missing required skills: {missing_required}
Missing preferred skills: {missing_preferred}
Candidate evidence:
{candidate_summary}
"""

INTERVIEW_PREP_PROMPT = """Generate interview preparation questions for this candidate and role.

Produce 6-8 questions total, using the "category" field for each:
- "technical": based on the job's required skills the candidate matched (test depth)
- "gap_related": based on missing required skills (how they'd approach/learn it)
- "behavioral": standard behavioral questions relevant to this role/responsibilities

Role: {role}
Matched required skills: {matched_required}
Missing required skills: {missing_required}
Key responsibilities: {responsibilities}
"""
