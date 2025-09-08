"""
nl2sql.py
---------
Guarded NL -> SQL for your recruiting DB.

- SELECT-only
- Whitelisted tables & columns
- Blocks dangerous keywords
- Adds LIMIT if missing
- JOIN hints for common relations
"""
from __future__ import annotations

import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI

# ----- Allowed base table/view names (we normalize schema-qualified names) -----
_ALLOWED_TABLES = {
    "resumes",
    "resumes_search",
    "jobdescription",   # "JobDescription"
    "candidatescore",   # "CandidateScore"
    "emailaudit",       # "EmailAudit"
}

# ----- Schema text for the LLM prompt -----
def _schema_text() -> str:
    # Make sure this matches what you actually create in ensure_schema() for your Postgres DB.
    return """
Tables / Views you may query (PostgreSQL):

public.resumes  -- VIEW (joined Candidate + ResumeDetails + Category)
  Columns:
    candidate_id                 int
    candidate_name               text
    candidate_email              text
    candidate_status             text
    candidate_created_at         timestamptz
    candidate_updated_at         timestamptz
    candidate_avatar             text
    candidate_skills             text[]        -- from Candidate."Skills"
    candidate_voice              text
    candidate_phone              text
    candidate_exam_url           text          -- Candidate."Exam_URL"
    candidate_temp_password      text          -- Candidate."tempPassword"
    candidate_temp_name          text          -- Candidate."temp_name"
    candidate_college            text
    candidate_exam_date          timestamptz   -- Candidate."Exam_date"
    candidate_expiry             timestamptz   -- Candidate."Expiry"

    resume_id                    int
    resume_candidate_id          int
    resume_name                  text
    resume_email                 text
    resume_phone                 text
    resume_skills                text[]        -- ResumeDetails.skills
    resume_ug_college            text
    resume_ug_cgpa               text
    resume_ug_yop                text
    resume_pg_college            text
    resume_pg_cgpa               text
    resume_pg_yop                text
    resume_projects              text[]        -- ResumeDetails.projects
    resume_certifications        text[]        -- ResumeDetails.certifications
    resume_experience            text[]        -- ResumeDetails.experience
    resume_file_name             text
    resume_processed_at          timestamptz

    category_ids                 int[]
    category_types               text[]
    category_created_ats         timestamptz[]
    category_text                text          -- comma-joined types

    full_name                    text          -- COALESCE(rd.name, c.name)
    email                        text          -- COALESCE(rd.email, c.email)

    technical_skills             text          -- array_to_string(resume_skills, ', ')
    work_experience              text          -- array_to_string(resume_experience, ' || ')
    projects_flat                text          -- array_to_string(resume_projects, ' || ')
    certifications_flat          text          -- array_to_string(resume_certifications, ', ')
    education                    text          -- UG/PG fields concatenated

    role_category                text NULL     -- placeholder (legacy)
    job_category                 text NULL     -- placeholder (legacy)
    current_role                 text NULL     -- placeholder (legacy)

public.resumes_search  -- MATERIALIZED VIEW (fast search corpus)
  Columns:
    candidate_id    int  (unique)
    full_name       text
    email           text
    candidate_email text
    category_text   text
    search_corpus   text  -- lower-cased concatenation of useful resume fields

public.jobescription
  Columns:
    id                          int (PK)
    job_description             text
    role_category               text
    categorization_confidence   numeric
    categorization_reasoning    text
    key_indicators              jsonb
    total_candidates_evaluated  int
    created_at                  timestamptz DEFAULT now()

public.CandidateScore
  Columns:
    id                 int (PK)
    job_id             int  -- FK -> JobDescription.id
    candidate_name     text
    resume_email       text NULL
    final_score        numeric
    final_rank         int
    detailed_reasoning text
    strengths          jsonb
    weaknesses         jsonb
    recommendation     text
    created_at         timestamptz DEFAULT now()

public.EmailAudit
  Columns:
    id               int (PK)
    sent_at          timestamptz DEFAULT now()
    job_id           bigint NULL
    candidate_name   text
    candidate_email  text
    email_type       text
    subject          text
    username         text NULL
    password         text NULL
    exam_link        text NULL
    send_status      text
    raw_result       jsonb NULL
""".strip()


# ----- NL2SQL validation helpers -----
def _normalize_table_name(raw: str) -> str | None:
    """
    Normalize a token appearing after FROM/JOIN:
    - ignore subqueries (tokens starting with '(')
    - strip alias/quotes/backticks
    - drop schema prefix (public.resumes -> resumes)
    """
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("("):
        return None
    s = s.rstrip(",)")
    s = re.split(r"\s+as\s+|\s+", s, flags=re.IGNORECASE)[0]
    s = s.strip('`"')
    if "." in s:
        s = s.split(".")[-1]
    return s.lower()

def _extract_tables(sql: str) -> set[str]:
    """Extract base table/view names from FROM/JOIN (schema-qualified ok)."""
    tables: set[str] = set()
    for m in re.finditer(r"(?is)\bfrom\s+([^\s,;()]+)", sql):
        t = _normalize_table_name(m.group(1))
        if t:
            tables.add(t)
    for m in re.finditer(r"(?is)\bjoin\s+([^\s,;()]+)", sql):
        t = _normalize_table_name(m.group(1))
        if t:
            tables.add(t)
    return tables

def _validate(sql: str) -> tuple[bool, str | None]:
    """
    Guardrails:
    - Only SELECT/CTE queries.
    - No INSERT/UPDATE/DELETE/DDL/other dangerous verbs.
    - All referenced base tables must be whitelisted in _ALLOWED_TABLES.
    """
    s = (sql or "").strip()

    forbidden = r"(?is)\b(insert|update|delete|merge|alter|drop|create|grant|revoke|truncate|vacuum|analyze|copy|call|do)\b"
    if re.search(forbidden, s):
        return False, "Only SELECT queries are allowed"

    if not re.search(r"(?is)\bselect\b", s):
        return False, "Query must contain SELECT"

    tables = _extract_tables(s)
    unknown = [t for t in tables if t not in _ALLOWED_TABLES]
    if unknown:
        return False, f"Table(s) not allowed: {', '.join(sorted(unknown))}"

    return True, None

def _ensure_limit(sql: str, default_limit: int = 100) -> str:
    """
    Add LIMIT to large listings if missing.
    - Keep COUNT(*) queries as-is.
    - Keep queries that already have LIMIT.
    """
    s = sql.strip()
    if re.search(r"(?is)\blimit\s+\d+\b", s):
        return s
    if re.search(r"(?is)\bcount\s*\(", s):
        return s
    return s + f" LIMIT {default_limit}"


# ----- NL2SQL class -----
class NL2SQL:
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            google_api_key=api_key,
            convert_system_message_to_human=True,
        )

    async def generate(self, question: str) -> str:
        """
        LLM-driven SQL generator (SELECT-only).
        The LLM decides columns, filters, joins, ordering, and limits.
        We enforce safety and do minimal post-processing.
        """
        schema = _schema_text()

        sys_prompt = (
            "You are a Postgres SQL writer. Return ONLY one valid SQL SELECT statement. "
            "Do not include explanations, comments, markdown code fences, or labels."
        )

        user_prompt = f"""
User question:
{question}

Database you may query (schema-qualified names preferred):
{schema}

Hard constraints:
- SELECT-only (no INSERT/UPDATE/DELETE/DDL, no COPY, no DO, no CALL).
- No semicolons at the end.
- Allowed relations ONLY:
  - public.resumes            -- a VIEW exposing candidate_* fields among others
  - public.CandidateScore
  - public.JobDescription
  - public.EmailAudit
  - public.resumes_search
- Prefer schema-qualified names (public.<table_or_view>).

Guidelines (use your judgement):
- Use LOWER(..) LIKE '%...%' for fuzzy text filters on free-form queries.
- If the user asks “how many”, return COUNT(*) AS cnt.
- For small listings, include a reasonable subset of columns; LIMIT large results to ≤ 100 rows.
- When “latest/most recent” is implied, order by created_at / sent_at DESC.
- To list ranked candidates, you MAY join:
    • public.CandidateScore.candidate_name ↔ LOWER(public.resumes.full_name) OR LOWER(public.resumes.candidate_name)
    • OR match emails: public.CandidateScore.resume_email ↔ public.resumes.email OR public.resumes.candidate_email
- For role/skill/location searches, consider relevant text columns in public.resumes
  (category_text, role_category, job_category, current_role, technical_skills, work_experience, education).
Return ONLY the SQL (no extra text).
SQL:
""".strip()

        out = await self.llm.ainvoke(sys_prompt + "\n\n" + user_prompt)
        text = (out.content or "").strip()

        # Strip wrappers (```sql ...```, "SQL:", etc.)
        text = re.sub(r"(?is)```(?:sql)?", "", text).strip()
        text = re.sub(r"(?is)^\s*SQL:\s*", "", text).strip()
        text = re.sub(r"(?is)^\s*sql\s*\n", "", text).strip()

        # Extract WITH ... SELECT ... FROM ... OR SELECT ... FROM ...
        m = re.search(r"(?is)\bwith\b\s+.+?\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)
        if not m:
            m = re.search(r"(?is)\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)
        sql = (m.group(0) if m else text).strip()

        # Enforce: must start with SELECT and no trailing semicolon
        sql = sql.rstrip(";")
        if not sql.lower().startswith("select"):
            raise ValueError(f"Generated SQL rejected: must start with SELECT.\nSQL: {sql}")

        ok, err = _validate(sql)
        if not ok:
            raise ValueError(f"Generated SQL rejected: {err}\nSQL: {sql}")

        return _ensure_limit(sql)
