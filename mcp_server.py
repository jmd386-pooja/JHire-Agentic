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
_db_manager = None

def get_resume_processor():
    global _resume_processor
    if _resume_processor is None:
        from mcp_tools import ResumeProcessor
        _resume_processor = ResumeProcessor()
        logger.info("Resume processor initialized")
    return _resume_processor

def get_database_manager():
    global _db_manager
    if _db_manager is None:
        from mcp_tools import DatabaseManager
        _db_manager = DatabaseManager()
        logger.info("Database manager initialized")
    return _db_manager

# ------------ FastMCP server ------------
mcp = FastMCP("resume-ranker-server")


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    try:
        db_status = "healthy"
        ai_status = "healthy"
        try:
            get_database_manager()
        except Exception as e:
            db_status = f"unhealthy: {e}"
        try:
            get_resume_processor()
        except Exception as e:
            ai_status = f"unhealthy: {e}"
        return {
            "server_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": db_status,
                "ai_model": ai_status,
            },
            "db_path": DB_PATH,
        }
    except Exception as e:
        return {"server_status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}

@mcp.tool()
async def get_database_stats() -> Dict[str, Any]:
    try:
        db = get_database_manager()
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
        db = get_database_manager()
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
    try:
        processor = get_resume_processor()
        results = processor.process_job_and_rank_candidates(job_description=job_description, top_n=top_n)
        resp: Dict[str, Any] = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_description_preview": (job_description[:200] + "...") if len(job_description) > 200 else job_description,
            "filtered_candidates": results.get("filtered_candidates", 0),
            "stored_in_db": results.get("stored_in_db", False),
        }
        if results.get("job_category"):
            jc = results["job_category"]
            resp["job_category"] = {
                "role_category": jc.role_category,
                "confidence_score": jc.confidence_score,
                "reasoning": jc.reasoning,
                "key_indicators": jc.key_indicators,
            }
        if results.get("initial_scores"):
            resp["initial_scores"] = [{
                "candidate_name": s.candidate_name,
                "initial_score": s.initial_score,
                "key_matches": s.key_matches,
                "areas_of_concern": s.areas_of_concern,
            } for s in results["initial_scores"]]
        if results.get("final_scores"):
            resp["final_rankings"] = [{
                "candidate_name": s.candidate_name,
                "final_score": s.final_score,
                "final_rank": s.final_rank,
                "detailed_reasoning": s.detailed_reasoning,
                "strengths": s.strengths,
                "weaknesses": s.weaknesses,
                "recommendation": s.recommendation,
            } for s in results["final_scores"]]
        if results.get("error"):
            resp["warning"] = results["error"]
        return resp
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

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
        ok = db.store_job_results(job_description, jc, finals)
        return {
            "status": "success" if ok else "error",
            "timestamp": datetime.now().isoformat(),
            "stored_successfully": bool(ok),
            "job_category": jc.role_category,
            "candidates_stored": len(final_scores_data),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

# ---- Core DB utilities exposed to clients ----

@mcp.tool()
async def execute_database_query(query: str) -> Dict[str, Any]:
    """
    SAFE SELECT-only query for the client (used by governing agent / NL2SQL).
    Returns: {"status":"success","data":[...]} or {"status":"error","error":...}
    """
    try:
        data = run_select(query)
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
async def db_info() -> Dict[str, Any]:
    """Report DB path, table list, rough counts, and distinct categories."""
    get_database_manager().ensure_schema_once()
    try:
        info: Dict[str, Any] = {"db_path": DB_PATH, "exists": os.path.exists(DB_PATH)}
        if info["exists"]:
            with get_conn() as cx:
                tables = [r["name"] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                info["tables"] = tables
                def one(q: str) -> int:
                    try:
                        r = cx.execute(q).fetchone()
                        return int(dict(r).get("c", 0)) if r else 0
                    except Exception:
                        return 0
                info["counts"] = {
                    "resumes": one("SELECT COUNT(*) AS c FROM resumes"),
                    "jobdescription": one("SELECT COUNT(*) AS c FROM jobdescription"),
                    "candidate_scores": one("SELECT COUNT(*) AS c FROM candidate_scores"),
                }
                dc = cx.execute(
                    "SELECT DISTINCT LOWER(category) AS category FROM resumes WHERE category IS NOT NULL LIMIT 50"
                ).fetchall()
                info["distinct_category"] = [d["category"] for d in dc]
        return {"status": "success", "data": info}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
async def get_job_history(limit: int = 10) -> Dict[str, Any]:
    """Recent jobs from jobdescription (paramized)."""
    try:
        rows = run_select_params(
            """
            SELECT id, job_description, role_category, categorization_confidence,
                   total_candidates_evaluated, created_at
            FROM jobdescription
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
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
    """Rankings for a job (paramized)."""
    try:
        rows = run_select_params(
            """
            SELECT candidate_name, final_score, final_rank, detailed_reasoning,
                   strengths, weaknesses, recommendation, created_at
            FROM candidate_scores
            WHERE job_id = ?
            ORDER BY final_rank ASC, candidate_name ASC
            """,
            (int(job_id),),
        )
        # normalize strengths/weaknesses if JSON
        for r in rows:
            for key in ("strengths", "weaknesses"):
                val = r.get(key)
                if isinstance(val, str):
                    try:
                        r[key] = json.loads(val)
                    except Exception:
                        r[key] = [val] if val else []
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "job_id": int(job_id),
            "candidates": rows,
            "total_candidates": len(rows),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

# ------------ Run FastMCP over stdio ------------
if __name__ == "__main__":
    # FastMCP run method name differs by version; this works across versions.
    if hasattr(mcp, "run"):
        try:
            # If run() is sync:
            mcp.run()
        except TypeError:
            # If run() is async coroutine:
            import asyncio
            asyncio.run(mcp.run())
    else:
        raise RuntimeError("Your fastmcp build has neither run() nor run_stdio(); please upgrade: pip install -U fastmcp")
