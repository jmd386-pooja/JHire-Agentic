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
from typing import Tuple

from langchain_google_genai import ChatGoogleGenerativeAI

ALLOWED_TABLES = {
    "resumes": [
        "id", "full_name", "email", "phone", "location", "category", "role_category", "job_category",
        "position_type", "technical_skills", "work_experience", "education", "certifications",
        "degrees", "projects", "languages", "soft_skills", "achievements", "linkedin_url",
        "github_url", "portfolio_url", "years_of_experience", "current_company", "current_role",
        "salary_expectations", "availability", "visa_status", "remote_preference",
    ],
    "candidate_scores": [
        "id", "job_id", "candidate_name", "resume_email", "final_rank", "match_score", "skills_score",
        "exp_score", "education_score", "location_score", "created_at",
    ],
    "jobdescription": [
        "id", "title", "description", "created_at", "location", "position_type", "category",
    ],
    "exam_credentials": [
        "candidate_email", "username", "password", "exam_link", "created_at",
    ],
}


def _schema_text() -> str:
    lines = []
    for t, cols in ALLOWED_TABLES.items():
        lines.append(f"- {t}(" + ", ".join(cols) + ")")
    return "\n".join(lines)


def _ensure_limit(sql: str, default_limit: int = 200) -> str:
    s = sql.strip().rstrip(";")
    if re.search(r"\blimit\b", s, re.IGNORECASE):
        return s
    return s + f" LIMIT {default_limit}"


def _validate(sql: str) -> Tuple[bool, str]:
    s = sql.strip().rstrip(";")

    # Accept either plain SELECT ... FROM ... or a CTE that leads into a SELECT
    if not (
        re.match(r"(?is)^\s*select\s+.+\s+from\s+.+", s)
        or re.match(r"(?is)^\s*with\s+.+?select\s+.+\s+from\s+.+", s)
    ):
        return False, "Only SELECT queries are allowed."

    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "grant", "revoke", "truncate"]
    if any(re.search(rf"\b{kw}\b", s, re.IGNORECASE) for kw in forbidden):
        return False, "Forbidden keyword detected."

    tables = re.findall(r"(?is)\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)|\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)", s)
    used = {t for pair in tables for t in pair if t}
    for t in used:
        if t not in ALLOWED_TABLES:
            return False, f"Table '{t}' not allowed."

    # If multiple tables, require explicit columns (no SELECT *)
    if re.search(r"(?is)\bselect\s+\*", s) and len(used) > 1:
        return False, "Use explicit column names when querying multiple tables."

    return True, ""


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
        We only enforce safety and lightly post-process the text.
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
              - public.candidate_scores
              - public.jobdescription
              - public.email_audit
            - Prefer schema-qualified names (public.<table_or_view>).

            Guidelines (not strict rules—use your best judgement):
            - Use LOWER(..) LIKE '%...%' for fuzzy text filters when the question is free-form.
            - If the user asks “how many”, return COUNT(*) as cnt.
            - For small listings, include a reasonable subset of columns; LIMIT large results to <= 100 rows.
            - When “latest” or “most recent” is implied, order by created_at / sent_at DESC as appropriate.
            - When listing ranked candidates, you MAY join:
                • public.candidate_scores.candidate_name ↔ LOWER(public.resumes.full_name) OR LOWER(public.resumes.candidate_name)
                • OR match emails: public.candidate_scores.resume_email ↔ public.resumes.email OR public.resumes.candidate_email
              Pick whichever is available/most reliable based on the question.
            - For role/skill/location searches, choose relevant text columns in public.resumes (e.g., category/role_category/job_category/current_role/technical_skills/work_experience/education).

            Return ONLY the SQL (no extra text).
            SQL:
        """

        out = await self.llm.ainvoke(sys_prompt + "\n" + user_prompt)
        text = (out.content or "").strip()

        # Remove common wrappers like ```sql ...``` or leading "SQL:" labels
        import re
        text = re.sub(r"(?is)```(?:sql)?", "", text).strip()
        text = re.sub(r"(?is)^\s*SQL:\s*", "", text).strip()
        text = re.sub(r"(?is)^\s*sql\s*\n", "", text).strip()

        # Extract the first WITH...SELECT or SELECT...FROM block
        m = re.search(r"(?is)\bwith\b\s+.+?\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)
        if not m:
            m = re.search(r"(?is)\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)
        sql = (m.group(0) if m else text).strip()

        # Enforce: SELECT-only, no trailing semicolon
        sql = sql.rstrip(";")
        if not sql.lower().startswith("select"):
            raise ValueError(f"Generated SQL rejected: must start with SELECT.\nSQL: {sql}")

        ok, err = _validate(sql)   # your existing validator: SELECT-only, allowed relations, etc.
        if not ok:
            raise ValueError(f"Generated SQL rejected: {err}\nSQL: {sql}")

        return _ensure_limit(sql)  # your existing helper to add a LIMIT when appropriate
