"""
MCP Server for AI-Powered Resume Processor & Ranker (FastMCP, stdio)

- Single SQLite selected by DATABASE_URL (falls back to ./jhire_resumes.db)
- Exposes:
    • health_check
    • get_database_stats
    • analyze_job_description
    • filter_resumes_by_category
    • initial_score_candidates
    • final_rank_candidates
    • process_complete_job
    • store_job_results
    • execute_database_query   (SAFE: SELECT-only)
    • db_info
    • get_job_history
    • get_candidate_rankings
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from fastmcp import FastMCP
import psycopg, psycopg.rows
from mcp_tools import DatabaseManager

# ------------ Env & Logging ------------
load_dotenv()

DEFAULT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "jhire_resumes.db"))
DB_PATH = os.environ.get("DATABASE_URL", DEFAULT_DB)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("resume-mcp-server")

# Windows console UTF-8, best-effort
if sys.platform.startswith("win"):
    try:
        os.system("chcp 65001 >nul 2>&1")
        os.environ["PYTHONIOENCODING"] = "utf-8"
    except Exception:
        pass

# ------------ SQLite helpers ------------
ALLOWED_SELECT = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)

def _pg_params():
    dsn = os.getenv("DATABASE_URL")
    return {"conninfo": dsn}

def pg_conn():
    # psycopg 3 connection
    return psycopg.connect(**{k: v for k, v in _pg_params().items() if v})

    
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def run_select(sql: str):
    sql = (sql or "").strip()
    if not sql.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in sql[:-1]:
        raise ValueError("Only a single statement is allowed.")
    with pg_conn() as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql)
        return list(cur.fetchall())

def run_select_params(sql: str, params: tuple):
    if not (sql or "").strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    with pg_conn() as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())

# ------------ Lazy tool helpers ------------
_resume_processor = None
db_manager = None

def get_resume_processor():
    global _resume_processor
    if _resume_processor is None:
        from mcp_tools import ResumeProcessor
        _resume_processor = ResumeProcessor()
        logger.info("Resume processor initialized")
    return _resume_processor

def get_database_manager():
    global db_manager
    if db_manager is None:
        from mcp_tools import DatabaseManager
        db_manager = DatabaseManager()
        # ensure views/MV/triggers exist
        try:
            db_manager.ensure_schema()
        except Exception as e:
            logger.warning(f"ensure_schema failed (will still run): {e}")
    return db_manager

try:
    db0 = get_database_manager()
    db0.ensure_schema_once()
    db0.refresh_resumes_search_if_dirty()
except Exception as e:
    logger.error("Bootstrap warning: %s", e)
    
_dbm = None
def _dbmgr() -> DatabaseManager:
    global _dbm
    if _dbm is None:
        _dbm = DatabaseManager()
    return _dbm


_BOOTSTRAPPED = False

def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set")
    return dsn

def _relation_exists(cur, schema: str, relname: str) -> bool:
    cur.execute(
        """
        SELECT to_regclass(%s)
        """,
        (f"{schema}.{relname}",),
    )
    return cur.fetchone()[0] is not None

def _create_resumes_view(cur) -> None:
    # Keep this in sync with your Prisma-backed schema
    cur.execute("""
    CREATE OR REPLACE VIEW public.resumes AS
      SELECT
        c.id                             AS candidate_id,
        c.name                           AS candidate_name,
        c.email                          AS candidate_email,
        c.status                         AS candidate_status,
        c."createdAt"                    AS candidate_created_at,
        c."updatedAt"                    AS candidate_updated_at,
        c."Avatar"                       AS candidate_avatar,
        c."Skills"                       AS candidate_skills,
        c."Voice"                        AS candidate_voice,
        c."ph_number"                    AS candidate_phone,
        c."Exam_URL"                     AS candidate_exam_url,
        c."tempPassword"                 AS candidate_temp_password,
        c."temp_name"                    AS candidate_temp_name,
        c."College"                      AS candidate_college,
        c."Exam_date"                    AS candidate_exam_date,
        c."Expiry"                       AS candidate_expiry,

        rd.id                            AS resume_id,
        rd."candidateId"                 AS resume_candidate_id,
        rd.name                          AS resume_name,
        rd.email                         AS resume_email,
        rd.phone                         AS resume_phone,
        rd.skills                        AS resume_skills,
        rd."UG_college"                  AS resume_ug_college,
        rd."UG_cgpa"                     AS resume_ug_cgpa,
        rd."UG_yop"                      AS resume_ug_yop,
        rd."PG_college"                  AS resume_pg_college,
        rd."PG_cgpa"                     AS resume_pg_cgpa,
        rd."PG_yop"                      AS resume_pg_yop,
        rd.projects                      AS resume_projects,
        rd.certifications                AS resume_certifications,
        rd.experience                    AS resume_experience,
        rd."fileName"                    AS resume_file_name,
        rd."processedAt"                 AS resume_processed_at,

        COALESCE(array_agg(DISTINCT cat.id)          FILTER (WHERE cat.id IS NOT NULL),          '{}'::int[])          AS category_ids,
        COALESCE(array_agg(DISTINCT cat.type)        FILTER (WHERE cat.type IS NOT NULL),        '{}'::text[])         AS category_types,
        COALESCE(array_agg(DISTINCT cat."createdAt") FILTER (WHERE cat."createdAt" IS NOT NULL), '{}'::timestamptz[])  AS category_created_ats,
        COALESCE(string_agg(DISTINCT cat.type, ','), '')                                         AS category_text,

        COALESCE(rd.name, c.name)      AS full_name,
        COALESCE(rd.email, c.email)    AS email,

        COALESCE(array_to_string(rd.skills, ', '), '')        AS technical_skills,
        COALESCE(array_to_string(rd.experience, ' || '), '')  AS work_experience,
        COALESCE(array_to_string(rd.projects, ' || '), '')    AS projects_flat,
        COALESCE(array_to_string(rd.certifications, ', '), '')AS certifications_flat,
        COALESCE(rd."UG_college",'') || ' ' ||
        COALESCE(rd."UG_cgpa",'')    || ' ' ||
        COALESCE(rd."UG_yop",'')     || ' ' ||
        COALESCE(rd."PG_college",'') || ' ' ||
        COALESCE(rd."PG_cgpa",'')    || ' ' ||
        COALESCE(rd."PG_yop",'')                               AS education,

        NULL::text AS role_category,
        NULL::text AS job_category,
        NULL::text AS current_role
      FROM "Candidate" c
      LEFT JOIN "ResumeDetails" rd ON rd."candidateId" = c.id
      LEFT JOIN "Category"      cat ON cat."candidateId" = c.id
      GROUP BY
        c.id, c.name, c.email, c.status, c."createdAt", c."updatedAt",
        c."Avatar", c."Skills", c."Voice", c."ph_number",
        c."Exam_URL", c."tempPassword", c."temp_name", c."College",
        c."Exam_date", c."Expiry",
        rd.id, rd."candidateId", rd.name, rd.email, rd.phone, rd.skills,
        rd."UG_college", rd."UG_cgpa", rd."UG_yop",
        rd."PG_college", rd."PG_cgpa", rd."PG_yop",
        rd.projects, rd.certifications, rd.experience,
        rd."fileName", rd."processedAt";
    """)

def _create_search_mv(cur) -> None:
    # create empty first (WITH NO DATA), indexes, then refresh
    cur.execute("""
      CREATE MATERIALIZED VIEW IF NOT EXISTS public.resumes_search AS
      SELECT
        r.candidate_id,
        r.full_name,
        r.email,
        r.candidate_email,
        r.category_text,
        LOWER(
          COALESCE(r.full_name,'')||' '||
          COALESCE(r.candidate_name,'')||' '||
          COALESCE(r.resume_name,'')||' '||
          COALESCE(r.candidate_status,'')||' '||
          COALESCE(r.category_text,'')||' '||
          COALESCE(r.technical_skills,'')||' '||
          COALESCE(r.work_experience,'')||' '||
          COALESCE(r.projects_flat,'')||' '||
          COALESCE(r.certifications_flat,'')||' '||
          COALESCE(r.education,'')||' '||
          COALESCE(r.candidate_college,'')||' '||
          COALESCE(r.resume_ug_college,'')||' '||
          COALESCE(r.resume_pg_college,'')
        ) AS search_corpus
      FROM public.resumes r
      WITH NO DATA;
    """)
    cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS resumes_search_uidx
                   ON public.resumes_search (candidate_id)""")
    cur.execute("""CREATE EXTENSION IF NOT EXISTS pg_trgm""")
    cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_trgm
                   ON public.resumes_search USING gin (search_corpus gin_trgm_ops)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_name_trgm
                   ON public.resumes_search USING gin (LOWER(full_name) gin_trgm_ops)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_email_trgm
                   ON public.resumes_search USING gin (LOWER(email) gin_trgm_ops)""")

def _create_refresh_state_and_triggers(cur) -> None:
    cur.execute("""
      CREATE TABLE IF NOT EXISTS public.resumes_refresh_state (
        id         int PRIMARY KEY DEFAULT 1,
        dirty      boolean NOT NULL DEFAULT true,
        updated_at timestamptz NOT NULL DEFAULT now()
      );
    """)
    cur.execute("""
      INSERT INTO public.resumes_refresh_state (id, dirty)
      VALUES (1, true)
      ON CONFLICT (id) DO NOTHING;
    """)
    cur.execute("""
      CREATE OR REPLACE FUNCTION public.mark_resumes_dirty()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        UPDATE public.resumes_refresh_state
           SET dirty = true, updated_at = now()
         WHERE id = 1;
        RETURN NULL;
      END $$;
    """)
    cur.execute("""DROP TRIGGER IF EXISTS trg_candidate_dirty ON "Candidate";""")
    cur.execute("""
      CREATE TRIGGER trg_candidate_dirty
      AFTER INSERT OR UPDATE OR DELETE ON "Candidate"
      FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();
    """)
    cur.execute("""DROP TRIGGER IF EXISTS trg_resumedetails_dirty ON "ResumeDetails";""")
    cur.execute("""
      CREATE TRIGGER trg_resumedetails_dirty
      AFTER INSERT OR UPDATE OR DELETE ON "ResumeDetails"
      FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();
    """)
    cur.execute("""DROP TRIGGER IF EXISTS trg_category_dirty ON "Category";""")
    cur.execute("""
      CREATE TRIGGER trg_category_dirty
      AFTER INSERT OR UPDATE OR DELETE ON "Category"
      FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();
    """)
    
def ensure_schema_once() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    try:
        ensure_schema()
        _BOOTSTRAPPED = True
    except Exception:
        logger.exception("ensure_schema_once failed; will retry on next call")
        
def refresh_resumes_search_if_dirty() -> None:
    dsn = _dsn()
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        # if MV is missing (e.g., DB reset), rebuild schema
        if not _relation_exists(cur, "public", "resumes_search"):
            ensure_schema()
            return
        cur.execute("SELECT dirty FROM public.resumes_refresh_state WHERE id = 1")
        row = cur.fetchone()
        if row and bool(row[0]):
            # CONCURRENTLY requires unique index (we created one)
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY public.resumes_search;")
            cur.execute("UPDATE public.resumes_refresh_state SET dirty=false WHERE id=1;")


# ------------ FastMCP server ------------
mcp = FastMCP("resume-ranker-server")


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    try:
        db = get_database_manager()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        exists_view = db.object_exists("view", "resumes")
        exists_mv   = db.object_exists("matview", "resumes_search")
        return {
            "server_status":"healthy",
            "timestamp": datetime.now().isoformat(),
            "components":{"database":"connected","views":{"resumes":exists_view,"resumes_search":exists_mv}}
        }
    except Exception as e:
        return {"server_status":"unhealthy","error":str(e),"timestamp":datetime.now().isoformat()}

@mcp.tool()
async def get_database_stats() -> Dict[str, Any]:
    try:
        db = _dbmgr()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        df = db.get_all_resumes()
        stats = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total_resumes": 0 if df is None or df.empty else int(len(df)),
            "db_path": DB_PATH,
        }
        if df is not None and not df.empty:
            stats.update({
                "columns": df.columns.tolist(),
                "sample_candidate_names": df.get("full_name", df.get("name", pd.Series(dtype=str))).head(3).tolist(),
                "database_shape": list(df.shape),
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            })
        return stats
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
def ensure_schema() -> None:
    """
    Idempotent bootstrap:
      - extensions
      - DROP old MV + VIEW (so we can change column names safely)
      - CREATE public.resumes (VIEW)
      - CREATE public.resumes_search (MATVIEW) + indexes
      - refresh_state + triggers
      - initial refresh
    """
    dsn = _dsn()
    # Use autocommit for DDL so one failure doesn't abort the whole transaction
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # 0) Extensions
            cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

            # 1) Drop dependent objects so column renames are allowed
            #    (CASCADE ensures anything depending on the view is removed)
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS public.resumes_search;")
            cur.execute("DROP VIEW IF EXISTS public.resumes CASCADE;")

            # 2) Re-create objects
            _create_resumes_view(cur)
            _create_refresh_state_and_triggers(cur)
            _create_search_mv(cur)

            # 3) Initial populate + clear dirty flag
            cur.execute("REFRESH MATERIALIZED VIEW public.resumes_search;")
            cur.execute("UPDATE public.resumes_refresh_state SET dirty=false WHERE id=1;")

    logger.info("Schema ensured (views/MV/indexes/refresh-state rebuilt).")


@mcp.tool()
async def bootstrap_schema() -> Dict[str, Any]:
    """Force-create/repair resumes view + mat view and refresh."""
    try:
        db = get_database_manager()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        ok_view = db.object_exists("view", "resumes")
        ok_mv   = db.object_exists("matview", "resumes_search")
        return {"status":"success","resumes_view":ok_view,"resumes_search":ok_mv,"timestamp":datetime.now().isoformat()}
    except Exception as e:
        return {"status":"error","error":str(e),"timestamp":datetime.now().isoformat()}

    
@mcp.tool()
async def analyze_job_description(job_description: str) -> Dict[str, Any]:
    try:
        processor = get_resume_processor()
        job_category = processor._categorize_job_description(job_description)
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "role_category": job_category.role_category,
            "confidence_score": job_category.confidence_score,
            "reasoning": job_category.reasoning,
            "key_indicators": job_category.key_indicators,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def filter_resumes_by_category(category: str, limit: int = 50) -> Dict[str, Any]:
    try:
        db = _dbmgr()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        processor = get_resume_processor()
        db = get_database_manager()
        df = db.get_all_resumes()
        if df is None or df.empty:
            return {"status": "error", "error": "No resumes found in database"}
        filtered_df = processor._filter_resumes_by_category(df, category)
        cands = []
        for idx, row in filtered_df.head(limit).iterrows():
            name = row.get("full_name", row.get("name", row.get("candidate_name", "Unknown")))
            cands.append({"name": name, "category": category, "id": int(row.get("id", idx))})
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "total_matches": int(len(filtered_df)),
            "returned_candidates": len(cands),
            "limit": limit,
            "candidates": cands,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def initial_score_candidates(job_description: str, category: str, limit: int = 20) -> Dict[str, Any]:
    try:
        
        processor = get_resume_processor()
        db = _dbmgr()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        df = db.get_all_resumes()
        if df is None or df.empty:
            return {"status": "error", "error": "No resumes found in database"}
        df = processor._prepare_resume_text(df)
        filtered_df = processor._filter_resumes_by_category(df, category)
        if filtered_df.empty:
            return {"status": "error", "error": f"No candidates found for category: {category}"}
        initial_scores = processor._initial_ai_scoring(filtered_df.head(limit), job_description)
        payload = [{
            "candidate_name": s.candidate_name,
            "initial_score": s.initial_score,
            "key_matches": s.key_matches,
            "areas_of_concern": s.areas_of_concern,
        } for s in initial_scores]
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_description_preview": (job_description[:200] + "...") if len(job_description) > 200 else job_description,
            "category": category,
            "candidates_scored": len(payload),
            "initial_scores": payload,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def final_rank_candidates(job_description: str, initial_scores_data: List[Dict[str, Any]], top_n: int = 10) -> Dict[str, Any]:
    try:
        from mcp_tools import InitialScore
        processor = get_resume_processor()
        initial_scores = [InitialScore(
            candidate_name=x["candidate_name"],
            initial_score=x["initial_score"],
            key_matches=x["key_matches"],
            areas_of_concern=x["areas_of_concern"],
        ) for x in initial_scores_data]
        final_scores = processor._final_llm_evaluation(initial_scores, job_description, top_n)
        payload = [{
            "candidate_name": s.candidate_name,
            "final_score": s.final_score,
            "final_rank": s.final_rank,
            "detailed_reasoning": s.detailed_reasoning,
            "strengths": s.strengths,
            "weaknesses": s.weaknesses,
            "recommendation": s.recommendation,
        } for s in final_scores]
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_description_preview": (job_description[:200] + "...") if len(job_description) > 200 else job_description,
            "candidates_ranked": len(payload),
            "top_n": top_n,
            "final_rankings": payload,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def process_complete_job(job_description: str, top_n: int = 10) -> Dict[str, Any]:
    """
    End-to-end pipeline:
      JD (must include explicit categories before the first ':') ->
      extract categories -> fetch resumes -> filter -> initial score ->
      final rank -> store in DB

    Returns detailed diagnostics and always sets 'status'.
    """
    from datetime import datetime
    import traceback

    try:
        # --- setup / preconditions ---
        db = _dbmgr()
        db.ensure_schema_once()
        db.refresh_resumes_search_if_dirty()
        processor = get_resume_processor()

        # --- 1) categories must be explicit in the JD header ---
        # Expected formats:
        #   "This Job Description categories are Data Science: <JD body...>"
        #   "This Job Description categories are Data Science, Full Stack: <JD body...>"
        explicit_categories = processor._extract_explicit_categories(job_description)
        if not explicit_categories:
            return {
                "status": "error",
                "error": (
                    "No category provided. Please prefix the JD like:\n"
                    "  'This Job Description categories are Data Science:'\n"
                    "or  'This Job Description categories are Data Science, Full Stack:'"
                ),
                "counts": {
                    "resumes_total": 0,
                    "filtered_candidates": 0,
                    "initial_scored": 0,
                    "final_ranked": 0,
                },
                "diagnostics": ["Missing explicit categories before the first colon (:)"],
                "timestamp": datetime.now().isoformat(),
            }

        # Build JobCategory (from mcp_tools, not from the processor object)
        from mcp_tools import JobCategory  # <-- correct import
        job_cat = JobCategory(
            role_category=explicit_categories[0],
            confidence_score=0.99,
            reasoning="User explicitly provided the category/categories in the JD header.",
            key_indicators=[f"explicit:{c}" for c in explicit_categories],
        )
        diagnostics = [
            f"role_category={job_cat.role_category} (confidence={job_cat.confidence_score})",
            f"explicit_categories={explicit_categories}",
        ]

        # --- 2) load resumes (as DataFrame) ---
        df_all = db.get_all_resumes()
        total = 0 if df_all is None else len(df_all)
        if df_all is None or df_all.empty:
            return {
                "status": "error",
                "error": "No resumes found in database",
                "job_category": job_cat.__dict__,
                "counts": {
                    "resumes_total": total,
                    "filtered_candidates": 0,
                    "initial_scored": 0,
                    "final_ranked": 0,
                },
                "diagnostics": diagnostics + ["public.resumes returned 0 rows"],
                "timestamp": datetime.now().isoformat(),
            }

        # --- 3) prepare text & filter by ANY of the explicit categories ---
        df_all = processor._prepare_resume_text(df_all)
        df_filtered = processor._filter_resumes_by_categories(df_all, explicit_categories)
        filtered = len(df_filtered)
        if filtered == 0:
            diagnostics.append(f"Filter produced 0 rows for categories={explicit_categories}")
            return {
                "status": "error",
                "error": f"No candidates found for categories: {explicit_categories}",
                "job_category": job_cat.__dict__,
                "counts": {
                    "resumes_total": total,
                    "filtered_candidates": 0,
                    "initial_scored": 0,
                    "final_ranked": 0,
                },
                "diagnostics": diagnostics,
                "timestamp": datetime.now().isoformat(),
            }

        # --- 4) initial scoring (widen input a bit to allow the model to choose) ---
        safe_top_n = max(1, int(top_n))
        seed_pool = max(safe_top_n * 3, 20)
        init_scores = processor._initial_ai_scoring(df_filtered.head(seed_pool), job_description)
        initial_scored = len(init_scores)
        if initial_scored == 0:
            diagnostics.append("Initial scoring returned 0 candidates")
            return {
                "status": "error",
                "error": "Initial scoring returned no candidates",
                "job_category": job_cat.__dict__,
                "counts": {
                    "resumes_total": total,
                    "filtered_candidates": filtered,
                    "initial_scored": 0,
                    "final_ranked": 0,
                },
                "diagnostics": diagnostics,
                "timestamp": datetime.now().isoformat(),
            }

        # --- 5) final ranking ---
        final_scores = processor._final_llm_evaluation(init_scores, job_description, safe_top_n)
        final_ranked = len(final_scores)
        if final_ranked == 0:
            diagnostics.append("Final ranking returned 0 candidates")
            return {
                "status": "error",
                "error": "Final ranking returned no candidates",
                "job_category": job_cat.__dict__,
                "counts": {
                    "resumes_total": total,
                    "filtered_candidates": filtered,
                    "initial_scored": initial_scored,
                    "final_ranked": 0,
                },
                "diagnostics": diagnostics,
                "timestamp": datetime.now().isoformat(),
            }

        # --- 6) persist results ---
        stored_ok, job_id = db.store_job_results(job_description, job_cat, final_scores)

        # Minimal payload back to client
        payload = [{
            "candidate_name": s.candidate_name,
            "final_score": s.final_score,
            "final_rank": s.final_rank,
            "detailed_reasoning": s.detailed_reasoning,
            "strengths": s.strengths,
            "weaknesses": s.weaknesses,
            "recommendation": s.recommendation,
        } for s in final_scores]

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_category": job_cat.__dict__,
            "counts": {
                "resumes_total": total,
                "filtered_candidates": filtered,
                "initial_scored": initial_scored,
                "final_ranked": final_ranked,
            },
            "final_rankings": payload,
            "stored_in_db": bool(stored_ok),
            "job_id": job_id,
            "diagnostics": diagnostics,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc(),
            "timestamp": datetime.now().isoformat(),
        }


# mcp_server.py
@mcp.tool()
async def store_job_results(job_description: str, job_category_data: Dict[str, Any], final_scores_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from mcp_tools import JobCategory, FinalScore
        db = get_database_manager()
        jc = JobCategory(
            role_category=job_category_data["role_category"],
            confidence_score=job_category_data["confidence_score"],
            reasoning=job_category_data["reasoning"],
            key_indicators=job_category_data["key_indicators"],
        )
        finals = [FinalScore(
            candidate_name=x["candidate_name"],
            final_score=x["final_score"],
            final_rank=x["final_rank"],
            detailed_reasoning=x["detailed_reasoning"],
            strengths=x["strengths"],
            weaknesses=x["weaknesses"],
            recommendation=x["recommendation"],
        ) for x in final_scores_data]

        stored_ok, job_id = db.store_job_results(job_description, jc, finals)

        return {
            "status": "success" if stored_ok else "error",
            "timestamp": datetime.now().isoformat(),
            "stored_successfully": bool(stored_ok),
            "job_id": job_id,
            "job_category": jc.role_category,
            "candidates_stored": len(final_scores_data),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    
# ---------- NEW: categorize → filter → initial rank → final rank → store ----------
@mcp.tool()
async def categorize_rank_and_store(
    jd_text: str,
    top_n: int = 20
) -> dict:
    """
    1) Classify JD to a role_category (rule-based keywords for determinism).
    2) Filter resumes by that category (fallback to all if none).
    3) Initial ranking via pg_trgm similarity against several resume fields.
    4) Final ranking = initial_score (+ small boost if category matched).
    5) Insert into public."JobDescription" and public."CandidateScore".
    Returns: {status, job_id, inserted, role_category, diagnostics, preview}
    """
    import os, re, json, psycopg
    from psycopg.rows import dict_row

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return {"status": "error", "error": "DATABASE_URL not set", "diagnostics": []}

    def _categorize(text: str) -> tuple[str, float, str, dict]:
        """
        Simple deterministic classifier (no LLM needed). 
        Returns: (category, confidence [0..1], reasoning, key_indicators_json)
        """
        t = (text or "").lower()
        cat, conf, why = "General", 0.35, "Default category"
        # ordered rules (first hit wins)
        rules = [
            ("Machine Learning",  ["ml ", "machine learning", "pytorch", "tensorflow", "deep learning", "computer vision", "nlp"]),
            ("Data Science",      ["data science", "statistics", "eda", "pandas", "notebook"]),
            ("Backend",           ["backend", "api", "microservice", "django", "node.js", "spring"]),
            ("Frontend",          ["frontend", "react", "next.js", "vue", "typescript", "angular"]),
            ("DevOps",            ["devops", "kubernetes", "terraform", "ci/cd", "sre"]),
            ("Cloud",             ["aws", "gcp", "azure", "serverless"]),
            ("Security",          ["security", "owasp", "iam", "siem"]),
            ("Mobile",            ["android", "ios", "react native", "flutter"]),
            ("Full Stack",        ["full stack", "end-to-end", "frontend and backend"]),
        ]
        for label, kws in rules:
            hits = [kw for kw in kws if kw in t]
            if hits:
                cat = label
                # confidence = min(1.0, 0.5 + 0.1 * hits) (cap at 1.0)
                conf = min(1.0, 0.5 + 0.1 * len(hits))
                why = f"Matched keywords: {', '.join(hits[:6])}"
                break

        # collect quick indicators
        inds = {
            "skills": sorted(list({k for _, kws in rules for k in kws if k in t}))[:20],
            "length_chars": len(t),
            "has_cloud": any(k in t for k in ["aws", "gcp", "azure", "cloud"]),
            "has_mlop": any(k in t for k in ["mlops", "deployment", "monitoring"]),
        }
        return cat, conf, why, inds

    diags = []
    jd = (jd_text or "").strip()
    if not jd:
        return {"status": "error", "error": "empty JD", "diagnostics": []}

    # classify
    role_category, conf, why, indicators = _categorize(jd)
    diags.append(f"role_category={role_category} conf={conf:.2f}")

    try:
        with psycopg.connect(dsn) as conn, conn.cursor(row_factory=dict_row) as cur:
            # sanity check resumes view
            cur.execute("""
                SELECT 1 FROM information_schema.views 
                WHERE table_schema='public' AND table_name='resumes'
            """)
            if not cur.fetchone():
                return {"status": "error", "error": "public.resumes view missing", "diagnostics": diags}

            # 1) Insert JobDescription (now includes categorization_confidence etc.)
            cur.execute("""
                INSERT INTO public."JobDescription"
                  (job_description, role_category, categorization_confidence, categorization_reasoning, key_indicators, total_candidates_evaluated)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (jd, role_category, float(conf), why, json.dumps(indicators), 0))
            job_id = cur.fetchone()["id"]

            # 2) Candidate pool: filter by category_text (fallback to all)
            cur.execute("""
                SELECT COUNT(*) AS c FROM public.resumes
                WHERE (category_text IS NOT NULL AND category_text <> '')
                  AND LOWER(category_text) LIKE LOWER('%' || %s || '%')
            """, (role_category,))
            pool = cur.fetchone()["c"] or 0

            pool_clause = """
                WHERE (category_text IS NOT NULL AND category_text <> '')
                  AND LOWER(category_text) LIKE LOWER('%' || %s || '%')
            """ if pool > 0 else ""
            if pool == 0:
                diags.append("no resumes matched category; ranking all resumes")

            # 3) Initial ranking via pg_trgm similarity across multiple fields
            #    Use COALESCE to avoid NULLs; pick GREATEST similarity as base_score
            base_query = f"""
                SELECT
                    COALESCE(full_name,'') AS candidate_name,
                    COALESCE(email,'')     AS resume_email,
                    GREATEST(
                      similarity(%s, COALESCE(resume_text,'')),
                      similarity(%s, COALESCE(technical_skills,'')),
                      similarity(%s, COALESCE(work_experience,'')),
                      similarity(%s, COALESCE(projects_flat,'')),
                      similarity(%s, COALESCE(certifications_flat,''))
                    ) AS base_score,
                    CASE
                      WHEN (category_text IS NOT NULL AND category_text <> '' 
                            AND LOWER(category_text) LIKE LOWER('%' || %s || '%'))
                      THEN 0.05 ELSE 0.0
                    END AS category_boost
                FROM public.resumes
                {pool_clause}
                ORDER BY base_score DESC
                LIMIT %s
            """

            params = [jd, jd, jd, jd, jd, role_category, max(1, int(top_n))]
            cur.execute(base_query, params if pool > 0 else params[:5] + params[-1:])  # remove role_category when no pool filter
            ranked = list(cur.fetchall())

            if not ranked:
                conn.rollback()
                return {"status":"error", "error":"ranking produced 0 rows", "diagnostics": diags + [f"pool={pool}"]}

            # 4) Final ranking (base + boost). Compute on client to keep it explicit, then store.
            final = []
            for r in ranked:
                base = float(r["base_score"] or 0.0)
                boost = float(r.get("category_boost") or 0.0)
                score = base + boost
                final.append({
                    "candidate_name": r["candidate_name"],
                    "resume_email": r["resume_email"],
                    "final_score": score
                })

            final.sort(key=lambda x: (-x["final_score"], x["candidate_name"]))
            # 5) Persist into CandidateScore
            inserted = 0
            for rank, row in enumerate(final, start=1):
                cur.execute("""
                    INSERT INTO public."CandidateScore"
                      (job_id, candidate_name, resume_email, final_rank, final_score, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (job_id, row["candidate_name"], row["resume_email"], rank, row["final_score"], role_category))
                inserted += cur.rowcount

            # update total evaluated count
            cur.execute("""UPDATE public."JobDescription"
                           SET total_candidates_evaluated = %s
                           WHERE id = %s
                        """, (len(final), job_id))

            conn.commit()

            preview = [
                {"final_rank": i+1, **final[i]}
                for i in range(min(5, len(final)))
            ]

            return {
                "status": "success",
                "job_id": job_id,
                "inserted": inserted,
                "role_category": role_category,
                "diagnostics": diags + [f"pool={pool}", f"inserted={inserted}"],
                "preview": preview
            }

    except Exception as e:
        return {"status": "error", "error": str(e), "diagnostics": diags}
    
    
# mcp_server.py
@mcp.tool()
async def rank_and_store_candidates(job_description_text: str, top_n: int = 20) -> dict:
    """
    Creates a JobDescription row, ranks candidates using pg_trgm similarity
    against the materialized view 'public.resumes_search' (search_corpus),
    persists results into public."CandidateScore", and returns diagnostics.
    """
    import json, traceback
    db = get_database_manager()
    conn = db.get_connection()
    diags = []

    text = (job_description_text or "").strip()
    if not text:
        return {"status": "error", "error": "Empty job description text", "diagnostics": ["empty JD"]}

    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Preconditions: view + matview should exist
            cur.execute("SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name='resumes'")
            if not cur.fetchone():
                return {"status": "error", "error": "resumes view missing", "diagnostics": ["public.resumes not found"]}

            cur.execute("SELECT 1 FROM pg_matviews WHERE schemaname='public' AND matviewname='resumes_search'")
            if not cur.fetchone():
                return {"status": "error", "error": "resumes_search matview missing", "diagnostics": ["public.resumes_search not found"]}

            # Count
            cur.execute("SELECT COUNT(*) AS c FROM public.resumes")
            total_resumes = int(cur.fetchone()["c"])
            if total_resumes == 0:
                return {"status": "error", "error": "no resumes in view", "diagnostics": ["public.resumes is empty"]}

            # Insert JobDescription (align exactly to your schema columns)
            cur.execute(
                """
                INSERT INTO public."JobDescription" (
                    job_description,
                    role_category,
                    categorization_confidence,
                    categorization_reasoning,
                    key_indicators,
                    total_candidates_evaluated
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (text, "auto", 0.0, "", json.dumps({"source": "rank_and_store_candidates"}), 0),
            )
            job_id = int(cur.fetchone()["id"])

            # Rank by trigram similarity using the materialized search corpus
            cur.execute(
                """
                SELECT
                    COALESCE(r.full_name, '') AS candidate_name,
                    COALESCE(r.email, '')     AS resume_email,
                    GREATEST(
                        similarity(%s, COALESCE(rs.search_corpus, '')),
                        similarity(%s, COALESCE(r.full_name, '')),
                        similarity(%s, COALESCE(r.email, ''))
                    ) AS sim
                FROM public.resumes r
                LEFT JOIN public.resumes_search rs
                  ON rs.candidate_id = r.candidate_id
                ORDER BY sim DESC
                LIMIT %s
                """,
                (text, text, text, max(1, int(top_n))),
            )
            ranked = cur.fetchall()
            if not ranked:
                conn.rollback()
                return {
                    "status": "error",
                    "error": "no candidates matched",
                    "diagnostics": [f"total_resumes={total_resumes}", "ranking returned 0 rows"],
                }

            # Persist into CandidateScore (only existing columns)
            inserted = 0
            for idx, row in enumerate(ranked, start=1):
                cur.execute(
                    """
                    INSERT INTO public."CandidateScore" (
                        job_id, candidate_name, resume_email, final_score, final_rank
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (job_id, row["candidate_name"], row["resume_email"], float(row["sim"]), idx),
                )
                inserted += cur.rowcount

            # Update evaluated count on the JobDescription row
            cur.execute(
                'UPDATE public."JobDescription" SET total_candidates_evaluated = %s WHERE id = %s',
                (inserted, job_id),
            )

            conn.commit()

            preview = [
                {
                    "candidate_name": r["candidate_name"],
                    "resume_email": r["resume_email"],
                    "final_rank": i + 1,
                    "final_score": float(r["sim"]),
                }
                for i, r in enumerate(ranked[: min(5, len(ranked))])
            ]

            return {
                "status": "success",
                "job_id": job_id,
                "inserted": inserted,
                "diagnostics": [f"total_resumes={total_resumes}", f"inserted={inserted}"],
                "preview": preview,
            }

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"status": "error", "error": str(e), "trace": traceback.format_exc(), "diagnostics": diags}


@mcp.tool()
async def top_ranked_for_job(job_id: int, limit: int = 10) -> dict:
    db = get_database_manager()
    conn = db.get_connection()
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("""
            SELECT candidate_name, resume_email, final_rank, final_score
            FROM public."CandidateScore"
            WHERE job_id = %s
            ORDER BY final_rank ASC
            LIMIT %s
        """, (int(job_id), int(limit)))
        rows = cur.fetchall()
    return {"status": "success", "data": rows}

    
# mcp_server.py  (ADD below store_job_results)

@mcp.tool()
async def upsert_exam_credentials(records: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Upsert exam credentials.
    records: [{"candidate_email":..., "username":..., "password":..., "exam_link":...}, ...]
    """
    try:
        if not records:
            return {"status": "success", "upserts": 0, "timestamp": datetime.now().isoformat()}

        db = get_database_manager()
        conn = db.get_connection()
        with conn.cursor() as cur:
            # Postgres-safe DDL
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.exam_credentials (
                    candidate_email TEXT PRIMARY KEY,
                    username        TEXT NOT NULL,
                    password        TEXT NOT NULL,
                    exam_link       TEXT NOT NULL,
                    created_at      timestamptz NOT NULL DEFAULT now()
                )
            """)
            # Parameterized upsert
            for r in records:
                cur.execute("""
                    INSERT INTO public.exam_credentials (candidate_email, username, password, exam_link)
                    VALUES (%(candidate_email)s, %(username)s, %(password)s, %(exam_link)s)
                    ON CONFLICT (candidate_email) DO UPDATE SET
                        username = EXCLUDED.username,
                        password = EXCLUDED.password,
                        exam_link = EXCLUDED.exam_link,
                        created_at = now()
                """, r)
        conn.commit()
        return {"status": "success", "upserts": len(records), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def log_email_audit(
    job_id: Optional[int],
    candidate_name: str,
    candidate_email: str,
    email_type: str,
    subject: str,
    username: Optional[str],
    password: Optional[str],
    exam_link: Optional[str],
    send_status: str,
    raw_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Insert a row into EmailAudit (matches Prisma schema: public."EmailAudit").
    """
    from datetime import datetime
    import json
    try:
        db = get_database_manager()
        conn = db.get_connection()
        with conn.cursor() as cur:
            # Ensure the Prisma-compatible table exists (quoted, mixed case)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public."EmailAudit"(
                  id              BIGSERIAL PRIMARY KEY,
                  sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
                  job_id          BIGINT,
                  candidate_name  TEXT,
                  candidate_email TEXT,
                  email_type      TEXT,
                  subject         TEXT,
                  username        TEXT,
                  password        TEXT,
                  exam_link       TEXT,
                  send_status     TEXT,
                  raw_result      JSONB
                )
            """)

            # Write into the quoted table name (NOT snake_case)
            cur.execute("""
                INSERT INTO public."EmailAudit"
                  (job_id, candidate_name, candidate_email, email_type, subject,
                   username, password, exam_link, send_status, raw_result)
                VALUES
                  (%(job_id)s, %(candidate_name)s, %(candidate_email)s, %(email_type)s, %(subject)s,
                   %(username)s, %(password)s, %(exam_link)s, %(send_status)s, %(raw_result)s::jsonb)
            """, {
                "job_id": job_id,
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "email_type": email_type,
                "subject": subject,
                "username": username,
                "password": password,
                "exam_link": exam_link,
                "send_status": send_status,
                "raw_result": json.dumps(raw_result, ensure_ascii=False),
            })

        conn.commit()
        return {"status": "success", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}



# ---- Core DB utilities exposed to clients ----
@mcp.tool()
async def execute_database_query(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    SELECT-only DB query. For INSERT/UPDATE/DDL, use dedicated write tools
    like `store_job_results`, `upsert_exam_credentials`, `log_email_audit`.
    """
    db = get_database_manager()
    db.ensure_schema_once()
    db.refresh_resumes_search_if_dirty()
    conn = db.get_connection()

    sql = (query or "").strip()
    # Reuse the compiled regex already in this file: ALLOWED_SELECT = r"^\s*SELECT\b"
    if not ALLOWED_SELECT.match(sql):
        return {
            "status": "error",
            "error": "Only SELECT queries are allowed via execute_database_query. Use dedicated write tools.",
            "query_preview": sql[:120],
            "timestamp": datetime.now().isoformat(),
        }

    def _run_once() -> Dict[str, Any]:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            data = [dict(r) for r in rows]
            return {
                "query": sql,
                "results_count": len(data),
                "data": data[:100],
                "columns": cols,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }

    try:
        return _run_once()

    except (psycopg.errors.UndefinedTable,
            psycopg.errors.UndefinedObject,
            psycopg.errors.InvalidSchemaName,
            psycopg.errors.InFailedSqlTransaction) as e:
        # Clear aborted tx, (re)create schema, retry once (matches your current pattern)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            db.ensure_schema_once()
            db.refresh_resumes_search_if_dirty()
        except Exception:
            pass
        try:
            return _run_once()
        except Exception as e2:
            return {"status": "error", "error": str(e2), "query": sql, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"status": "error", "error": str(e), "query": sql, "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def db_info() -> Dict[str, Any]:
    """
    Report Postgres database info:
      - server_version
      - list of tables in public schema
      - approximate row counts via pg_class.reltuples
      - distinct categories from public.resumes (if exists)
    """
    try:
        db = get_database_manager()
        conn = db.get_connection()
        info: Dict[str, Any] = {}

        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Server version
            cur.execute("SHOW server_version")
            info["server_version"] = cur.fetchone()["server_version"]

            # All tables in public
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [r["table_name"] for r in cur.fetchall()]
            info["tables"] = tables

            # Approximate row counts (avoid COUNT(*) on big tables)
            # reltuples is a planner estimate; good enough for a dashboard
            cur.execute("""
                SELECT c.relname AS table_name,
                       COALESCE(c.reltuples, 0)::bigint AS approx_rows
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
            """)
            counts = {r["table_name"]: int(r["approx_rows"]) for r in cur.fetchall()}
            info["approx_counts"] = counts

            # Distinct categories from public.resumes (if it exists)
            cur.execute("""
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='public' AND table_name='resumes'
            """)
            if cur.fetchone():
                cur.execute("""
                    SELECT DISTINCT LOWER(category_text) AS category
                    FROM public.resumes
                    WHERE category_text IS NOT NULL AND category_text <> ''
                    LIMIT 50
                """)
                info["distinct_category"] = [r["category"] for r in cur.fetchall()]
            else:
                info["distinct_category"] = []

        return {"status": "success", "data": info, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


@mcp.tool()
async def get_job_history(limit: int = 10) -> Dict[str, Any]:
    """Recent jobs from JobDescription (parameterized, psycopg3-safe)."""
    try:
        db = get_database_manager()
        conn = db.get_connection()
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    job_description,
                    role_category,
                    categorization_confidence,
                    categorization_reasoning,
                    key_indicators,
                    total_candidates_evaluated,
                    created_at
                FROM "JobDescription"
                ORDER BY created_at DESC, id DESC
                LIMIT %(limit)s
                """,
                {"limit": int(limit)},
            )
            rows = cur.fetchall() or []
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_history": rows,
            "total_jobs": len(rows),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def get_candidate_rankings(job_id: int) -> Dict[str, Any]:
    """Rankings for a job (parameterized, psycopg3-safe)."""
    try:
        db = get_database_manager()
        conn = db.get_connection()
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                    candidate_name,
                    final_score,
                    final_rank,
                    detailed_reasoning,
                    strengths,
                    weaknesses,
                    recommendation,
                    created_at
                FROM "CandidateScore"
                WHERE job_id = %(job_id)s
                ORDER BY final_rank ASC, candidate_name ASC
                """,
                {"job_id": int(job_id)},
            )
            rows = cur.fetchall() or []

        for r in rows:
            for key in ("strengths", "weaknesses"):
                val = r.get(key)
                if isinstance(val, str):
                    try:
                        r[key] = json.loads(val)
                    except Exception:
                        r[key] = [val] if val else []
                elif val is None:
                    r[key] = []
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_id": int(job_id),
            "candidates": rows,
            "total_candidates": len(rows),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

# --- CLI entry point for packaging ---
def main() -> None:
    """
    Starts the MCP server. Kept tiny so it's safe to call from console_scripts.
    """
    import asyncio
    asyncio.run(mcp.run())  


if __name__ == "__main__":
    main()
