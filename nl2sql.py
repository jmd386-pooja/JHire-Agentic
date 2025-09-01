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
        prompt = f"""
            You are a SQL generator over a recruiting database. Output ONLY a valid SQL SELECT statement.
            Rules:
            1) SELECT-only (no INSERT/UPDATE/DELETE/DDL).
            2) Allowed tables/columns:
            {_schema_text()}

            Guidelines:
            - Prefer LOWER(..) LIKE for fuzzy text filters.
            - Prefer explicit columns instead of * for multi-table queries.
            - Use safe JOINs via explicit keys: resumes.email <-> candidate_scores.resume_email, candidate_scores.job_id <-> jobdescription.id
            - If the user asks to "list emails of Django folks in Bangalore", select resumes.full_name, resumes.email with WHERE filters.
            - If they ask "how many", use COUNT(*). For "top N" by rank, ORDER BY candidate_scores.final_rank ASC.
            - If timeframe is implied ("latest job"), order jobdescription.created_at DESC and LIMIT 1 in a subquery.

            Return ONLY the SQL (no explanations, no markdown).
            User question: {question}
            SQL:
        """
        out = await self.llm.ainvoke(prompt)
        text = (out.content or "").strip()

        # Strip common wrappers: code fences and language tags
        # ```sql ... ```  or ``` ... ```
        text = re.sub(r"(?is)```(?:sql)?", "", text).strip()
        # Leading "SQL:" label
        text = re.sub(r"(?is)^\s*SQL:\s*", "", text).strip()
        # A lone first-line "sql"
        text = re.sub(r"(?is)^\s*sql\s*\n", "", text).strip()

        # Extract the first SELECT ... FROM ... (or WITH ... SELECT ... FROM ...)
        m = re.search(r"(?is)\bwith\b\s+.+?\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)
        if not m:
            m = re.search(r"(?is)\bselect\b\s+.+?\bfrom\b\s+.+?(?=;|$)", text)

        if m:
            sql = m.group(0).strip()
        else:
            # fallback: use the whole thing
            sql = text

        sql = sql.strip().rstrip(";")

        ok, err = _validate(sql)
        if not ok:
            raise ValueError(f"Generated SQL rejected: {err}\nSQL: {sql}")

        return _ensure_limit(sql)
