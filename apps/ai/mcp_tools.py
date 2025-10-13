"""
AI-Powered Resume Processor & Ranker

This system analyzes a single job description, automatically categorizes the role,
filters relevant resumes from SQLite database, performs AI-powered ranking, and then uses LLM for
final perfect scoring with detailed reasoning. Results are stored back to SQLite.
"""
import re
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
import psycopg, psycopg.rows

import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import threading
_bootstrapped = False
_bootstrap_lock = threading.Lock()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MODEL_NAME = "gemini-2.0-flash-thinking-exp"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TOP_N = 10

# Database configuration
PG_DSN = os.getenv('DATABASE_URL')

def pg_conn():
    if not PG_DSN:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(PG_DSN)


class JobCategory(BaseModel):
    """Primary + (optional) multiple categories when user provides more than one."""
    role_category: str = Field(description="Primary role category (canonical key)")
    all_categories: List[str] = Field(default_factory=list, description="All canonical categories inferred or explicitly provided")
    confidence_score: float = Field(description="Confidence 0.0–1.0")
    reasoning: str = Field(description="Why these categories were chosen")
    key_indicators: List[str] = Field(description="Key terms/phrases indicating the category")



class InitialScore(BaseModel):
    """Pydantic model for initial AI scoring."""
    candidate_name: str = Field(description="Full name of the candidate")
    initial_score: float = Field(description="Initial compatibility score from 0.0 to 1.0")
    key_matches: List[str] = Field(description="Key skills/experiences that match the job requirements")
    areas_of_concern: List[str] = Field(description="Areas where the candidate might need improvement")


class FinalScore(BaseModel):
    """Pydantic model for final LLM scoring and ranking."""
    candidate_name: str = Field(description="Full name of the candidate")
    final_score: float = Field(description="Final perfect score from 0.0 to 1.0")
    final_rank: int = Field(description="Final ranking position (1 being the best)")
    detailed_reasoning: str = Field(description="Comprehensive explanation of why this score and rank were given")
    strengths: List[str] = Field(description="Candidate's key strengths for this role")
    weaknesses: List[str] = Field(description="Candidate's areas for improvement")
    recommendation: str = Field(description="Final recommendation")


class DatabaseManager:
    """Manages PostgreSQL database connections and operations."""
    
    def __init__(self):
        """Initialize database connection."""
        self.connection = None
        self._connect()
        self.ensure_schema_once()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.connection = pg_conn()
            logging.getLogger(__name__).info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_connection(self):
        # No schema work here — just ensure a live connection.
        if self.connection is None or getattr(self.connection, "closed", True):
            self._connect()
        return self.connection
    
    def ensure_schema(self) -> None:
        """
        Create/repair:
          • Extensions: pg_trgm, unaccent
          • Tables: JobDescription, CandidateScore, EmailAudit (+ FK, indexes, updated_at triggers)
          • VIEW: public.resumes (Candidate ⟷ ResumeDetails ⟷ Category)
          • MATERIALIZED VIEW: public.resumes_search (+ GIN trigram, name/email trigram)
          • Refresh state + triggers to mark resumes_search dirty
          • Initial refresh of resumes_search
        """
        import psycopg
        from psycopg.rows import dict_row

        conn = self.get_connection()
        prev_ac = getattr(conn, "autocommit", False)
        try:
            conn.autocommit = True
        except Exception:
            pass

        with conn.cursor(row_factory=dict_row) as cur:
            # ---------------- Extensions ----------------
            cur.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')
            cur.execute('CREATE EXTENSION IF NOT EXISTS "unaccent";')

            # ---------------- JobDescription ----------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS public."JobDescription"(
              id BIGSERIAL PRIMARY KEY,
              job_description            TEXT NOT NULL,
              role_category              TEXT NOT NULL,
              categorization_confidence  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
              categorization_reasoning   TEXT NOT NULL DEFAULT '',
              key_indicators             JSONB NOT NULL DEFAULT '{}'::jsonb,
              total_candidates_evaluated INTEGER NOT NULL DEFAULT 0,
              created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public."AgentTrajectory" (
                    id BIGSERIAL PRIMARY KEY,
                    start_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    user_goal TEXT NOT NULL,
                    steps JSONB NOT NULL,
                    final_answer TEXT,
                    confidence DOUBLE PRECISION
                );
                """
            )
            # backfill columns/defaults if table existed with older shape
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS job_description            TEXT;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS role_category              TEXT;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS categorization_confidence  DOUBLE PRECISION;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS categorization_reasoning   TEXT;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS key_indicators             JSONB;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS total_candidates_evaluated INTEGER;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS created_at                 TIMESTAMPTZ NOT NULL DEFAULT now();""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ADD COLUMN IF NOT EXISTS updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now();""")
            cur.execute("""UPDATE public."JobDescription" SET categorization_confidence = 0.0
                           WHERE categorization_confidence IS NULL;""")
            cur.execute("""UPDATE public."JobDescription" SET categorization_reasoning = ''
                           WHERE categorization_reasoning IS NULL;""")
            cur.execute("""UPDATE public."JobDescription" SET key_indicators = '{}'::jsonb
                           WHERE key_indicators IS NULL;""")
            cur.execute("""UPDATE public."JobDescription" SET total_candidates_evaluated = 0
                           WHERE total_candidates_evaluated IS NULL;""")
            cur.execute("""ALTER TABLE public."JobDescription"
                ALTER COLUMN job_description            SET NOT NULL,
                ALTER COLUMN role_category              SET NOT NULL,
                ALTER COLUMN categorization_confidence  SET DEFAULT 0.0,
                ALTER COLUMN categorization_confidence  SET NOT NULL,
                ALTER COLUMN categorization_reasoning   SET DEFAULT '',
                ALTER COLUMN categorization_reasoning   SET NOT NULL,
                ALTER COLUMN key_indicators             SET DEFAULT '{}'::jsonb,
                ALTER COLUMN key_indicators             SET NOT NULL,
                ALTER COLUMN total_candidates_evaluated SET DEFAULT 0,
                ALTER COLUMN total_candidates_evaluated SET NOT NULL;""")

            # ---------------- CandidateScore ----------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS public."CandidateScore"(
              id BIGSERIAL PRIMARY KEY,
              job_id             BIGINT NOT NULL,
              candidate_name     TEXT NOT NULL,
              resume_email       TEXT,
              final_score        DOUBLE PRECISION NOT NULL,
              final_rank         INTEGER NOT NULL,
              detailed_reasoning TEXT NOT NULL DEFAULT '',
              strengths          JSONB NOT NULL DEFAULT '[]'::jsonb,
              weaknesses         JSONB NOT NULL DEFAULT '[]'::jsonb,
              recommendation     TEXT NOT NULL DEFAULT '',
              created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """)
            # ensure columns/defaults
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS job_id             BIGINT;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS candidate_name     TEXT;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS resume_email       TEXT;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS final_score        DOUBLE PRECISION;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS final_rank         INTEGER;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS detailed_reasoning TEXT NOT NULL DEFAULT '';""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS strengths          JSONB NOT NULL DEFAULT '[]'::jsonb;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS weaknesses         JSONB NOT NULL DEFAULT '[]'::jsonb;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS recommendation     TEXT NOT NULL DEFAULT '';""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS created_at         TIMESTAMPTZ NOT NULL DEFAULT now();""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ NOT NULL DEFAULT now();""")

            # enforce not-null set
            cur.execute("""UPDATE public."CandidateScore" SET detailed_reasoning = ''
                           WHERE detailed_reasoning IS NULL;""")
            cur.execute("""UPDATE public."CandidateScore" SET strengths = '[]'::jsonb
                           WHERE strengths IS NULL;""")
            cur.execute("""UPDATE public."CandidateScore" SET weaknesses = '[]'::jsonb
                           WHERE weaknesses IS NULL;""")
            cur.execute("""UPDATE public."CandidateScore" SET recommendation = ''
                           WHERE recommendation IS NULL;""")
            cur.execute("""ALTER TABLE public."CandidateScore"
                ALTER COLUMN job_id         SET NOT NULL,
                ALTER COLUMN candidate_name SET NOT NULL,
                ALTER COLUMN final_score    SET NOT NULL,
                ALTER COLUMN final_rank     SET NOT NULL;""")

            # FK (add if missing)
            cur.execute("""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'candidatescore_job_id_fkey'
              ) THEN
                ALTER TABLE public."CandidateScore"
                  ADD CONSTRAINT candidatescore_job_id_fkey
                  FOREIGN KEY (job_id)
                  REFERENCES public."JobDescription"(id)
                  ON DELETE CASCADE;
              END IF;
            END;
            $$;
            """)
            # helpful indexes
            cur.execute("""CREATE INDEX IF NOT EXISTS idx_candidatescore_job_rank
                           ON public."CandidateScore"(job_id, final_rank);""")
            cur.execute("""CREATE INDEX IF NOT EXISTS candidatescore_name_lower_idx
                           ON public."CandidateScore"(LOWER(candidate_name));""")
            cur.execute("""CREATE INDEX IF NOT EXISTS candidatescore_email_idx
                           ON public."CandidateScore"(resume_email);""")


            # ---------------- updated_at trigger fn ----------------
            cur.execute("""
            CREATE OR REPLACE FUNCTION public.set_updated_at()
            RETURNS trigger AS $$
            BEGIN
              NEW.updated_at := now();
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """)
            # triggers for updated_at
            cur.execute("""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_jobdescription_updated_at') THEN
                CREATE TRIGGER trg_jobdescription_updated_at
                BEFORE UPDATE ON public."JobDescription"
                FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_candidatescore_updated_at') THEN
                CREATE TRIGGER trg_candidatescore_updated_at
                BEFORE UPDATE ON public."CandidateScore"
                FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
              END IF;
            END;
            $$;
            """)

            # ---------------- VIEW: public.resumes ----------------
            cur.execute("""
                CREATE OR REPLACE VIEW public.resumes AS
                SELECT
                  c.id                                 AS candidate_id,
                  c.name                               AS candidate_name,
                  c.email                              AS candidate_email,
                  c.status                             AS candidate_status,
                  c."createdAt"                        AS candidate_created_at,
                  c."updatedAt"                        AS candidate_updated_at,
                  c."Avatar"                           AS candidate_avatar,
                  c."Skills"                           AS candidate_skills,
                  c."Voice"                            AS candidate_voice,
                  c."ph_number"                        AS candidate_phone,
                  c."Exam_URL"                         AS candidate_exam_url,
                  c."tempPassword"                     AS candidate_temp_password,
                  c."temp_name"                        AS candidate_temp_name,
                  c."College"                          AS candidate_college,
                  c."Exam_date"                        AS candidate_exam_date,
                  c."Expiry"                           AS candidate_expiry,

                  rd.id                                AS resume_id,
                  rd."candidateId"                     AS resume_candidate_id,
                  rd.name                              AS resume_name,
                  rd.email                             AS resume_email,
                  rd.phone                             AS resume_phone,
                  rd.skills                            AS resume_skills,
                  rd."UG_college"                      AS resume_ug_college,
                  rd."UG_cgpa"                         AS resume_ug_cgpa,
                  rd."UG_yop"                          AS resume_ug_yop,
                  rd."PG_college"                      AS resume_pg_college,
                  rd."PG_cgpa"                         AS resume_pg_cgpa,
                  rd."PG_yop"                          AS resume_pg_yop,
                  rd.projects                          AS resume_projects,
                  rd.certifications                    AS resume_certifications,
                  rd.experience                        AS resume_experience,
                  rd."fileName"                        AS resume_file_name,
                  rd."processedAt"                     AS resume_processed_at,

                  -- keep array types STABLE and explicit
                  COALESCE(
                    array_agg(DISTINCT cat.id) FILTER (WHERE cat.id IS NOT NULL),
                    ARRAY[]::integer[]
                  ) AS category_ids,

                  COALESCE(
                    array_agg(DISTINCT cat.type) FILTER (WHERE cat.type IS NOT NULL),
                    ARRAY[]::text[]
                  ) AS category_types,

                  COALESCE(
                    array_agg(DISTINCT cat."createdAt") FILTER (WHERE cat."createdAt" IS NOT NULL),
                    ARRAY[]::timestamptz[]
                  ) AS category_created_ats,

                  COALESCE(string_agg(DISTINCT cat.type, ','), '') AS category_text,

                  COALESCE(rd.name,  c.name)  AS full_name,
                  COALESCE(rd.email, c.email) AS email,

                  COALESCE(array_to_string(rd.skills, ', '), '')        AS technical_skills,
                  COALESCE(array_to_string(rd.experience, ' || '), '')  AS work_experience,
                  COALESCE(array_to_string(rd.projects,  ' || '), '')   AS projects_flat,
                  COALESCE(array_to_string(rd.certifications, ', '), '')AS certifications_flat,

                  COALESCE(rd."UG_college",'') || ' ' ||
                  COALESCE(rd."UG_cgpa",'')    || ' ' ||
                  COALESCE(rd."UG_yop",'')     || ' ' ||
                  COALESCE(rd."PG_college",'') || ' ' ||
                  COALESCE(rd."PG_cgpa",'')    || ' ' ||
                  COALESCE(rd."PG_yop",'')     AS education,

                  NULL::text AS role_category,
                  NULL::text AS job_category,
                  NULL::text AS current_role
                FROM "Candidate" c
                LEFT JOIN "ResumeDetails" rd ON rd."candidateId" = c.id
                LEFT JOIN "Category"       cat ON cat."candidateId" = c.id
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

            # ---------------- MAT VIEW: public.resumes_search ----------------
            # create once if missing (no IF NOT EXISTS for matviews prior to recent PG; use catalog check)
            cur.execute("""
            SELECT 1 FROM pg_matviews
            WHERE schemaname='public' AND matviewname='resumes_search';
            """)
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute("""
                CREATE MATERIALIZED VIEW public.resumes_search AS
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
            # indexes on mat view
            cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS resumes_search_uidx
                           ON public.resumes_search (candidate_id);""")
            cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_trgm
                           ON public.resumes_search USING gin (search_corpus gin_trgm_ops);""")
            cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_name_trgm
                           ON public.resumes_search USING gin (LOWER(full_name) gin_trgm_ops);""")
            cur.execute("""CREATE INDEX IF NOT EXISTS resumes_search_email_trgm
                           ON public.resumes_search USING gin (LOWER(email) gin_trgm_ops);""")

            # ---------------- refresh state + triggers ----------------
            cur.execute("""
            CREATE TABLE IF NOT EXISTS public.resumes_refresh_state (
              id int PRIMARY KEY DEFAULT 1,
              dirty boolean NOT NULL DEFAULT true,
              updated_at timestamptz NOT NULL DEFAULT now()
            );
            """)
            cur.execute("""INSERT INTO public.resumes_refresh_state (id, dirty)
                           VALUES (1, true) ON CONFLICT (id) DO NOTHING;""")
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
            cur.execute('DROP TRIGGER IF EXISTS trg_candidate_dirty ON "Candidate";')
            cur.execute('CREATE TRIGGER trg_candidate_dirty AFTER INSERT OR UPDATE OR DELETE ON "Candidate" FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();')
            cur.execute('DROP TRIGGER IF EXISTS trg_resumedetails_dirty ON "ResumeDetails";')
            cur.execute('CREATE TRIGGER trg_resumedetails_dirty AFTER INSERT OR UPDATE OR DELETE ON "ResumeDetails" FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();')
            cur.execute('DROP TRIGGER IF EXISTS trg_category_dirty ON "Category";')
            cur.execute('CREATE TRIGGER trg_category_dirty AFTER INSERT OR UPDATE OR DELETE ON "Category" FOR EACH STATEMENT EXECUTE FUNCTION public.mark_resumes_dirty();')

            # ---------------- initial refresh ----------------
            try:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY public.resumes_search;")
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute("REFRESH MATERIALIZED VIEW public.resumes_search;")

        try:
            conn.autocommit = prev_ac
        except Exception:
            pass



    def object_exists(self, kind: str, name: str) -> bool:
        """Check existence of a view/matview/table in public schema."""
        conn = self.get_connection()
        with conn.cursor() as cur:
            try:
                if kind == "matview":
                    cur.execute("SELECT 1 FROM pg_matviews WHERE schemaname='public' AND matviewname=%s", (name,))
                elif kind == "view":
                    cur.execute("SELECT 1 FROM information_schema.views WHERE table_schema='public' AND table_name=%s", (name,))
                else:
                    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (name,))
                return cur.fetchone() is not None
            except Exception:
                try: conn.rollback()
                except Exception: pass
                return False



    def refresh_resumes_search_if_dirty(self) -> None:
        conn = self.get_connection()
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT dirty FROM public.resumes_refresh_state WHERE id = 1")
                row = cur.fetchone()
                dirty = bool(row[0]) if row else True
            except psycopg.errors.UndefinedTable:
                # previous SELECT put the tx in an aborted state → rollback before creating
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.resumes_refresh_state (
                      id int PRIMARY KEY DEFAULT 1,
                      dirty boolean NOT NULL DEFAULT true,
                      updated_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    INSERT INTO public.resumes_refresh_state (id, dirty)
                    VALUES (1, true)
                    ON CONFLICT (id) DO NOTHING
                """)
                dirty = True
    
            if dirty:
                try:
                    cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY public.resumes_search")
                except Exception:
                    # refresh failed mid-tx → rollback and try plain refresh
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    cur.execute("REFRESH MATERIALIZED VIEW public.resumes_search")
    
                # mark clean
                try:
                    cur.execute("UPDATE public.resumes_refresh_state SET dirty=false WHERE id=1")
                except Exception:
                    # if that UPDATE failed for any reason, rollback once and continue
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    cur.execute("UPDATE public.resumes_refresh_state SET dirty=false WHERE id=1")
    
        try:
            conn.commit()
        except Exception:
            pass



        
    def ensure_schema_once(self):
        global _bootstrapped
        if _bootstrapped:
            return
        with _bootstrap_lock:
            if _bootstrapped:
                return
            try:
                self.ensure_schema()
                _bootstrapped = True
            except Exception:
                # never let schema errors print to stdout or kill the process
                logging.getLogger(__name__).exception("ensure_schema failed (will retry later)")



    def _insert_sample_resumes(self, cursor):
        """Insert sample resume data for testing."""
        sample_resumes = [
            {
                'full_name': 'John Doe',
                'email': 'puvvulasaigowtham@gmail.com',
                'category': 'data science',
                'technical_skills': 'Python, Machine Learning, TensorFlow, SQL, Statistics',
                'work_experience': '3 years as Data Scientist at TechCorp',
                'education': 'MS in Computer Science'
            },
            {
                'full_name': 'Jane Smith',
                'email': 'puvvulasaigowtham@gmail.com',
                'category': 'data engineering',
                'technical_skills': 'Python, SQL, ETL, Apache Spark, Hadoop, AWS',
                'work_experience': '2 years as Data Engineer at DataFlow Inc',
                'education': 'BS in Data Science'
            },
            {
                'full_name': 'Mike Johnson',
                'email': 'puvvulasaigowtham@gmail.com',
                'category': 'full stack',
                'technical_skills': 'JavaScript, React, Node.js, Python, PostgreSQL, AWS',
                'work_experience': '4 years as Full Stack Developer at WebTech',
                'education': 'BS in Software Engineering'
            },
            {
                'full_name': 'Sarah Wilson',
                'email': 'puvvulasaigowtham@gmail.com',
                'category': 'data science',
                'technical_skills': 'Python, R, Scikit-learn, Pandas, NumPy, Data Visualization',
                'work_experience': '1 year as ML Engineer at AI Startup',
                'education': 'PhD in Statistics'
            },
            {
                'full_name': 'David Brown',
                'email': 'puvvulasaigowtham@gmail.com',
                'category': 'platform engineering',
                'technical_skills': 'Docker, Kubernetes, AWS, Terraform, Python, Linux',
                'work_experience': '5 years as DevOps Engineer at CloudCorp',
                'education': 'BS in Computer Engineering'
            }
        ]
        
        for resume in sample_resumes:
            cursor.execute("""
                INSERT INTO resumes (full_name, email, category, technical_skills, work_experience, education)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                resume['full_name'],
                resume['email'],
                resume['category'],
                resume['technical_skills'],
                resume['work_experience'],
                resume['education']
            ))
        
        logger.info(f"Inserted {len(sample_resumes)} sample resumes")
    
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def get_all_resumes(self) -> pd.DataFrame:
        self.ensure_schema_once()
        self.refresh_resumes_search_if_dirty()
        conn = self.get_connection()
        try:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT * FROM public.resumes")
                return pd.DataFrame(cur.fetchall())
        except psycopg.errors.UndefinedTable:
            # Fallback inline join with same column names your pipeline expects
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("""
                    SELECT
                      c.id AS candidate_id,
                      COALESCE(rd.name,c.name) AS full_name,
                      COALESCE(rd.email,c.email) AS email,
                      c.email AS candidate_email,
                      c."Exam_URL"     AS candidate_exam_url,
                      c."tempPassword" AS candidate_temp_password,
                      c."temp_name"    AS candidate_temp_name,
                      c."Exam_date"    AS candidate_exam_date,
                      c."Expiry"       AS candidate_expiry,
                      COALESCE(string_agg(DISTINCT cat.type, ','),'') AS category_text,
                      COALESCE(array_to_string(rd.skills, ', '), '')       AS technical_skills,
                      COALESCE(array_to_string(rd.experience, ' || '), '') AS work_experience,
                      COALESCE(array_to_string(rd.projects, ' || '), '')   AS projects_flat,
                      COALESCE(array_to_string(rd.certifications, ', '), '') AS certifications_flat,
                      COALESCE(rd."UG_college",'')||' '||
                      COALESCE(rd."UG_cgpa",'')   ||' '||
                      COALESCE(rd."UG_yop",'')    ||' '||
                      COALESCE(rd."PG_college",'')||' '||
                      COALESCE(rd."PG_cgpa",'')   ||' '||
                      COALESCE(rd."PG_yop",'')    AS education,
                      NULL::text AS role_category,
                      NULL::text AS job_category,
                      NULL::text AS current_role
                    FROM "Candidate" c
                    LEFT JOIN "ResumeDetails" rd ON rd."candidateId" = c.id
                    LEFT JOIN "Category"      cat ON cat."candidateId" = c.id
                    GROUP BY
                      c.id, rd.name, rd.email, rd.skills, rd.experience, rd.projects, rd.certifications,
                      c."Exam_URL", c."tempPassword", c."temp_name", c."Exam_date", c."Expiry",
                      rd."UG_college", rd."UG_cgpa", rd."UG_yop",
                      rd."PG_college", rd."PG_cgpa", rd."PG_yop"
                """)
                return pd.DataFrame(cur.fetchall())


    
    def store_job_results(
            self,
            job_description: str,
            job_category: JobCategory,
            final_scores: List[FinalScore],
        ) -> tuple[bool, Optional[int]]:
        """
        Store one JobDescription row + all CandidateScore rows.
        Return (ok, job_id).
        """
        if not job_description or not job_description.strip():
            logger.error("store_job_results: empty job_description")
            return False, None
        if not final_scores:
            logger.warning("store_job_results: no final_scores to store")
            return False, None
    
        conn = self.connection
        if conn is None:
            logger.error("store_job_results: no DB connection")
            return False, None
    
        try:
            with conn.cursor() as cur:
                # 1) JobDescription
                cur.execute(
                    """
                    INSERT INTO "JobDescription" (
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
                    (
                        job_description,
                        job_category.role_category,
                        float(job_category.confidence_score or 0.0),
                        job_category.reasoning or "",
                        json.dumps(getattr(job_category, "key_indicators", [])),
                        len(final_scores),
                    ),
                )
                job_id = cur.fetchone()[0]
                logger.info('store_job_results: inserted "JobDescription" id=%s', job_id)
    
                # 2) Prepare email lookup
                # Prefer a direct hit by name in the resumes view (which already coalesces rd.email/c.email)
                email_lookup_sql = """
                    SELECT email
                    FROM public.resumes
                    WHERE LOWER(full_name) = LOWER(%s)
                    LIMIT 1
                """
    
                # 3) Insert CandidateScore rows (with looked-up email)
                sql_score = """
                    INSERT INTO "CandidateScore" (
                        job_id,
                        candidate_name,
                        resume_email,
                        final_score,
                        final_rank,
                        detailed_reasoning,
                        strengths,
                        weaknesses,
                        recommendation
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
    
                for s in final_scores:
                    # Best-effort email resolution
                    email = getattr(s, "email", "") or ""
                    if not email:
                        try:
                            cur.execute(email_lookup_sql, (s.candidate_name,))
                            row = cur.fetchone()
                            email = row[0] if row and row[0] else ""
                        except Exception as e:
                            logger.warning("email lookup failed for %r: %s", s.candidate_name, e)
                            email = ""
    
                    cur.execute(
                        sql_score,
                        (
                            job_id,
                            s.candidate_name,
                            email,
                            float(s.final_score or 0.0),
                            int(s.final_rank or 0),
                            s.detailed_reasoning or "",
                            json.dumps(s.strengths or []),
                            json.dumps(s.weaknesses or []),
                            s.recommendation or "",
                        ),
                    )
    
            conn.commit()
            return True, job_id
        except Exception as e:
            logger.error("store_job_results failed: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
            return False, None
    

class ResumeProcessor:
    """Advanced AI-powered resume processor with automatic categorization and dual-scoring."""
    
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the ResumeProcessor with Gemini AI model."""
        self.model_name = model_name
        self.temperature = temperature
        self.llm = None
        self.db_manager = DatabaseManager()
        self._initialize_llm()
    
    def _initialize_llm(self) -> None:
        """Initialize the LangChain LLM with Gemini AI."""
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not found.")
            
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                google_api_key=api_key,
                convert_system_message_to_human=True
            )
            logger.info(f"Initialized Gemini AI model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI model: {e}")
            raise
    def _normalize_categories(self, raw: List[str]) -> List[str]:
        """Map free-text categories to canonical keys used across the system."""
        canon = {
            "data_science":        {"data science","data scientist","ml","ml engineer","ai","ai engineer","machine learning"},
            "data_engineering":    {"data engineering","data engineer","etl","etl developer","big data","spark","hadoop"},
            "full_stack":          {"full stack","fullstack","web","web developer","frontend+backend"},
            "platform_engineering":{"platform","platform engineering","devops","sre","infrastructure","cloud"},
            "consulting":          {"consulting","consultant","advisory","strategy"},
            "software_engineering":{"software","software engineering","software engineer","developer","programmer"},
            "product_management":  {"product","product management","product manager","pm","product owner","program manager"},
            "ui_ux_design":        {"ui/ux","ui ux","ux","ui","design","designer","visual design","product design"},
        }
        out = []
        for s in (raw or []):
            t = s.strip().lower()
            if not t: 
                continue
            matched = None
            for key, alts in canon.items():
                if t == key or t in alts:
                    matched = key; break
                # substring fallback (e.g., "ml/data science")
                if any(a in t for a in alts):
                    matched = key; break
            if not matched:
                # last resort: keep as-is (lets LLM still use it downstream)
                matched = t.replace(" ", "_")
            out.append(matched)
        # unique, stable order
        seen, uniq = set(), []
        for k in out:
            if k not in seen:
                seen.add(k); uniq.append(k)
        return uniq

    def _load_resumes_from_db(self) -> pd.DataFrame:
        """Load resumes from SQLite database."""
        try:
            logger.info("Loading resumes from database...")
            df = self.db_manager.get_all_resumes()
            logger.info(f"Successfully loaded {len(df)} resumes from database")
            
            if df.empty:
                raise ValueError("No resumes found in database.")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading resumes from database: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _prepare_resume_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """Combine ALL columns from resumes into a structured text blob for AI processing.
        Robust to lists/arrays/Series/dicts/NaNs.
        """
        import numpy as np
        df = df.copy()

        def _clean_value(v) -> str:
            """Return a clean human string for any value; empty '' if nothing useful."""
            # Fast path for None-like
            if v is None:
                return ""

            # Flatten lists/tuples/sets
            if isinstance(v, (list, tuple, set)):
                parts = [s for s in (_clean_value(x) for x in v) if s]
                return ", ".join(parts)

            # Flatten pandas/NumPy array-ish
            if isinstance(v, (pd.Series, np.ndarray)):
                parts = [s for s in (_clean_value(x) for x in list(v)) if s]
                return ", ".join(parts)

            # Flatten dict
            if isinstance(v, dict):
                parts = [f"{k}: {_clean_value(val)}" for k, val in v.items() if _clean_value(val)]
                return ", ".join(parts)

            # Scalar: skip NaN/empties
            try:
                if pd.isna(v):
                    return ""
            except Exception:
                pass

            s = str(v).strip()
            if not s:
                return ""
            if s.lower() in {"nan", "none", "null", "{}", "[]"}:
                return ""
            return s

        combined_texts: list[str] = []
        for _, row in df.iterrows():
            text_parts: list[str] = []

            # Candidate "name" heading
            name = row.get("full_name", row.get("name", row.get("candidate_name", "Unknown")))
            text_parts.append(f"CANDIDATE: {name}")

            # Add every other column as KEY: value
            for column in df.columns:
                if column.lower() in {"full_name", "name", "candidate_name", "id"}:
                    continue
                clean = _clean_value(row.get(column, ""))
                if clean:
                    text_parts.append(f"{column.upper()}: {clean}")

            combined_texts.append("\n".join(text_parts))

        df["combined_text"] = combined_texts
        return df

    
    def _extract_explicit_categories(self, jd: str) -> List[str]:
        """
        Accepts patterns like:
          - "This Job Description categories are Data Science: <JD...>"
          - "categories are: Data Science / Full Stack: <JD...>"
          - "category: data engineering and platform engineering: <JD...>"
        Returns canonicalized categories (via _normalize_categories).
        """
        text = (jd or "").strip()
        if not text:
            return []

        # Preferred: stop at the first colon right after the categories list
        m = re.search(r"\b(?:this\s+job\s+description\s+)?categories?\s+are\s+(.+?)\s*:", text, re.IGNORECASE)
        frag: str
        if m:
            frag = m.group(1)
        else:
            # Fallback: generic "category/categories is|are|:" on a single line,
            # but still cut at the first colon to avoid eating the whole JD.
            m2 = re.search(r"\bcategories?\b\s*(?:is|are|:)\s*(.+)", text, re.IGNORECASE)
            if not m2:
                return []
            frag = m2.group(1).splitlines()[0]
            frag = frag.split(":", 1)[0]  # hard stop before the JD body

        # Split the category list by common delimiters
        parts = re.split(r"\s*(?:,|/|;|\band\b|&|\+)\s*", frag, flags=re.IGNORECASE)
        parts = [p for p in parts if p]
        return self._normalize_categories(parts)


    def _categorize_job_description(self, job_description: str) -> JobCategory:
        """Use explicit categories if provided; otherwise ask the LLM (and allow multi)."""
        try:
            # 1) Explicit categories (fast path)
            explicit = self._extract_explicit_categories(job_description)
            if explicit:
                primary = explicit[0]
                return JobCategory(
                    role_category=primary,
                    all_categories=explicit,
                    confidence_score=0.99,
                    reasoning="User explicitly provided the category/categories in the job description.",
                    key_indicators=[f"explicit:{c}" for c in explicit]
                )

            # 2) LLM-based categorization (allowing multiple)
            prompt = f"""
                You are an expert recruiter. Read the job description and output a JSON object with:
                - role_category: the single best primary category (one of: data_science, data_engineering, full_stack,
                  platform_engineering, consulting, software_engineering, product_management, ui_ux_design)
                - all_categories: array of zero or more categories (same canonical set) that also reasonably apply
                - confidence_score: 0.0–1.0
                - reasoning: short explanation
                - key_indicators: array of brief phrases from the JD that hint at these categories

                JOB DESCRIPTION:
                {job_description}
            """
            parser = PydanticOutputParser(pydantic_object=JobCategory)
            fmt = parser.get_format_instructions()
            messages = [HumanMessage(content=f"{prompt}\n\n{fmt}")]
            response = self.llm.invoke(messages)
            text = response.content or ""

            # unwrap ```json fences if present
            if "```json" in text:
                s = text.find("```json") + 7
                e = text.find("```", s)
                text = text[s:e].strip()

            jc = parser.parse(text)

            # Ensure canonicalization just in case the LLM drifts
            all_canon = self._normalize_categories(jc.all_categories or [jc.role_category])
            jc.all_categories = all_canon
            jc.role_category = all_canon[0] if all_canon else jc.role_category

            return jc

        except Exception as e:
            logger.error(f"Error categorizing job description: {e}")
            # fallback can also produce multi when keywords hit multiple buckets
            fb = self._fallback_categorization(job_description)
            # make sure all_categories at least contains primary
            if not getattr(fb, "all_categories", None):
                fb.all_categories = [fb.role_category]
            return fb
        
    def _filter_resumes_by_categories(self, df: pd.DataFrame, categories: List[str]) -> pd.DataFrame:
        """Union of candidates matching ANY of the given categories (case-insensitive)."""
        import numpy as np

        if df is None or df.empty:
            return df

        raw = [str(c).strip().lower() for c in (categories or []) if str(c).strip()]
        if not raw:
            return df

        SYN = {
            "data_science":         {"data science","data scientist","ml","machine learning","ml engineer","ai","ai engineer"},
            "data_engineering":     {"data engineering","data engineer","etl","big data","spark","hadoop"},
            "full_stack":           {"full stack","fullstack"},
            "platform_engineering": {"platform engineering","platform","devops","sre","infrastructure","cloud"},
            "software_engineering": {"software engineering","software engineer","backend","frontend"},
            "product_management":   {"product management","product manager","pm"},
            "consulting":           {"consulting","consultant","advisory"},
            "ui_ux_design":         {"ui/ux","ui","ux","design","designer"},
        }

        def _expand(c: str) -> set:
            al = {c, c.replace("_", " ")}
            al |= SYN.get(c, set())
            return {a.strip().lower() for a in al if a and a.strip()}

        ALL_ALIASES = set()
        for c in raw:
            ALL_ALIASES |= _expand(c)

        def _as_list(v):
            if v is None:
                return []
            if isinstance(v, (list, tuple, set)):
                return list(v)
            if isinstance(v, (np.ndarray, pd.Series)):
                return list(v)
            return [v]

        kept = []
        for i, row in df.iterrows():
            cat_text = str(row.get("category_text") or "").lower()
            types_raw = _as_list(row.get("category_types"))
            cat_types = {str(x).strip().lower() for x in types_raw if str(x).strip()}

            if any(a in cat_text for a in ALL_ALIASES) or (ALL_ALIASES & cat_types):
                kept.append(i)

        if not kept:
            return df.iloc[0:0].copy()
        unique_idx = list(dict.fromkeys(kept))  # order-preserving de-dupe of row indices
        return df.loc[unique_idx].reset_index(drop=True)




    
    def _fallback_categorization(self, job_description: str) -> JobCategory:
        """Fallback categorization using keyword matching."""
        job_lower = job_description.lower()
        
        # Simple keyword-based categorization
        if any(term in job_lower for term in ['machine learning', 'data science', 'ml', 'ai', 'statistical']):
            category = 'data_science'
        elif any(term in job_lower for term in ['data engineer', 'etl', 'pipeline', 'hadoop', 'spark']):
            category = 'data_engineering'
        elif any(term in job_lower for term in ['full stack', 'frontend', 'backend', 'web development']):
            category = 'full_stack'
        elif any(term in job_lower for term in ['platform', 'devops', 'infrastructure', 'cloud']):
            category = 'platform_engineering'
        elif any(term in job_lower for term in ['consulting', 'advisory', 'strategy', 'client']):
            category = 'consulting'
        else:
            category = 'software_engineering'
        
        return JobCategory(
            role_category=category,
            confidence_score=0.7,
            reasoning="Fallback categorization using keyword matching",
            key_indicators=["Keyword-based fallback"]
        )
    
    def _filter_resumes_by_category(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """Return resumes whose category_text or category_types match the given category (case-insensitive)."""
        import numpy as np

        if df is None or df.empty:
            return df

        cat = (category or "").strip().lower()
        if not cat:
            return df

        SYN = {
            "data_science":         {"data science","data scientist","ml","machine learning","ml engineer","ai","ai engineer"},
            "data_engineering":     {"data engineering","data engineer","etl","big data","spark","hadoop"},
            "full_stack":           {"full stack","fullstack"},
            "platform_engineering": {"platform engineering","platform","devops","sre","infrastructure","cloud"},
            "software_engineering": {"software engineering","software engineer","backend","frontend"},
            "product_management":   {"product management","product manager","pm"},
            "consulting":           {"consulting","consultant","advisory"},
            "ui_ux_design":         {"ui/ux","ui","ux","design","designer"},
        }

        def _as_list(v):
            if v is None:
                return []
            if isinstance(v, (list, tuple, set)):
                return list(v)
            if isinstance(v, (np.ndarray, pd.Series)):
                return list(v)
            return [v]

        aliases = {cat, cat.replace("_", " ")}
        aliases |= SYN.get(cat, set())
        aliases = {a.strip().lower() for a in aliases if a and a.strip()}

        kept = []
        for i, row in df.iterrows():
            cat_text = str(row.get("category_text") or "").lower()
            types_raw = _as_list(row.get("category_types"))
            cat_types = {str(x).strip().lower() for x in types_raw if str(x).strip()}

            if any(a in cat_text for a in aliases) or (aliases & cat_types):
                kept.append(i)

        # Deduplicate indices (order preserving) to avoid drop_duplicates hashing list columns
        if not kept:
            return df.iloc[0:0].copy()
        unique_idx = list(dict.fromkeys(kept))
        return df.loc[unique_idx].reset_index(drop=True)





    
    def _fallback_scoring(self, category_df: pd.DataFrame, job_description: str) -> List[InitialScore]:
        """Fallback scoring method when AI scoring fails."""
        logger.info("Using fallback scoring method due to AI processing issues")
        
        fallback_scores = []
        for idx, row in category_df.iterrows():
            try:
                # Simple keyword-based scoring
                job_lower = job_description.lower()
                resume_lower = row['combined_text'].lower()
                
                # Count matching keywords
                job_words = set(job_lower.split())
                resume_words = set(resume_lower.split())
                common_words = job_words.intersection(resume_words)
                
                # Calculate basic score (0.0 to 1.0)
                score = min(len(common_words) / max(len(job_words), 1), 1.0)
                
                # Create fallback score object
                fallback_score = InitialScore(
                    candidate_name=row.get('full_name', 'Unknown'),
                    initial_score=score,
                    key_matches=list(common_words)[:5],
                    areas_of_concern=["Fallback scoring used - AI processing unavailable"]
                )
                
                fallback_scores.append(fallback_score)
                logger.info(f"Fallback score for {fallback_score.candidate_name}: {fallback_score.initial_score:.3f}")
                
            except Exception as e:
                logger.error(f"Error in fallback scoring for candidate: {e}")
                continue
        
        return fallback_scores
    
    def _initial_ai_scoring(self, category_df: pd.DataFrame, job_description: str) -> List[InitialScore]:
        """Perform initial AI scoring of candidates."""
        if category_df.empty:
            return []
        
        logger.info(f"Performing initial AI scoring for {len(category_df)} candidates...")
        
        scored_candidates = []
        
        for idx, row in category_df.iterrows():
            try:
                logger.info(f"Processing candidate: {row.get('full_name', 'Unknown')}")
                
                prompt = f"""
                You are an expert HR professional evaluating a candidate for a position.
                
                JOB DESCRIPTION:
                {job_description}
                
                CANDIDATE RESUME:
                {row['combined_text']}
                
                Please provide an initial compatibility score and analysis.
                """
                
                # Create output parser
                parser = PydanticOutputParser(pydantic_object=InitialScore)
                format_instructions = parser.get_format_instructions()
                full_prompt = f"{prompt}\n\n{format_instructions}"
                
                logger.info(f"Sending request to Gemini AI for candidate: {row.get('full_name', 'Unknown')}")
                
                # Get AI response
                messages = [
                    HumanMessage(content=full_prompt)
                ]
                
                response = self.llm.invoke(messages)
                logger.info(f"Received response from Gemini AI for candidate: {row.get('full_name', 'Unknown')}")
                
                # Parse the response
                response_text = response.content
                logger.info(f"Response content length: {len(response_text)}")
                
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                logger.info(f"Parsed JSON text: {json_text[:200]}...")
                
                score_result = parser.parse(json_text)
                scored_candidates.append(score_result)
                
                logger.info(f"Initial score for {score_result.candidate_name}: {score_result.initial_score:.3f}")
                
            except Exception as e:
                logger.error(f"Error scoring candidate {row.get('full_name', 'Unknown')}: {e}")
                logger.error(f"Full error details: {str(e)}")
                continue
        
        logger.info(f"Successfully scored {len(scored_candidates)} out of {len(category_df)} candidates")
        
        # If no candidates were scored by AI, use fallback scoring
        if not scored_candidates:
            logger.warning("AI scoring failed for all candidates, using fallback scoring")
            scored_candidates = self._fallback_scoring(category_df, job_description)
        
        return scored_candidates
    
    def _fallback_final_evaluation(
        self, 
        scored_candidates: List[InitialScore], 
        top_n: int
    ) -> List[FinalScore]:
        """Fallback final evaluation when LLM fails."""
        logger.info("Using fallback final evaluation method due to LLM processing issues")
        
        # Sort by initial score and take top N
        top_candidates = sorted(scored_candidates, key=lambda x: x.initial_score, reverse=True)[:top_n]
        
        fallback_scores = []
        for i, candidate in enumerate(top_candidates):
            try:
                # Create fallback final score
                fallback_final = FinalScore(
                    candidate_name=candidate.candidate_name,
                    final_score=candidate.initial_score,  # Use initial score as final
                    final_rank=i + 1,  # Simple sequential ranking
                    detailed_reasoning="Fallback evaluation used - LLM processing unavailable",
                    strengths=candidate.key_matches,
                    weaknesses=candidate.areas_of_concern,
                    recommendation="Consider" if candidate.initial_score > 0.5 else "Not Recommended"
                )
                
                fallback_scores.append(fallback_final)
                logger.info(f"Fallback final score for {fallback_final.candidate_name}: Score {fallback_final.final_score:.3f}, Rank {fallback_final.final_rank}")
                
            except Exception as e:
                logger.error(f"Error in fallback final evaluation for {candidate.candidate_name}: {e}")
                continue
        
        return fallback_scores
    
    def _final_llm_evaluation(
        self, 
        scored_candidates: List[InitialScore], 
        job_description: str,
        top_n: int
    ) -> List[FinalScore]:
        """Use LLM for final perfect scoring and ranking with detailed reasoning."""
        if not scored_candidates:
            logger.warning("No scored candidates provided for final evaluation")
            return []
        
        # Sort by initial score and take top N
        top_candidates = sorted(scored_candidates, key=lambda x: x.initial_score, reverse=True)[:top_n]
        
        logger.info(f"Performing final LLM evaluation for top {len(top_candidates)} candidates...")
        
        final_scores = []
        
        for candidate in top_candidates:
            try:
                logger.info(f"Final evaluation for candidate: {candidate.candidate_name}")
                
                # Individual candidate evaluation
                individual_prompt = f"""
                You are a senior HR director and technical hiring expert. Your task is to provide the FINAL perfect scoring and ranking for a candidate.

                JOB DESCRIPTION:
                {job_description}

                CANDIDATE ANALYSIS:
                Name: {candidate.candidate_name}
                Initial Score: {candidate.initial_score:.3f}
                Key Matches: {', '.join(candidate.key_matches)}
                Areas of Concern: {', '.join(candidate.areas_of_concern)}

                Provide your final evaluation with:
                1. FINAL PERFECT SCORE (0.0 to 1.0) - your expert assessment
                2. FINAL RANKING (1 = best, {len(top_candidates)} = lowest)
                3. Detailed reasoning for score and rank
                4. Specific strengths and weaknesses
                5. Final recommendation
                """
                
                # Create output parser
                parser = PydanticOutputParser(pydantic_object=FinalScore)
                format_instructions = parser.get_format_instructions()
                full_prompt = f"{individual_prompt}\n\n{format_instructions}"
                
                logger.info(f"Sending final evaluation request to Gemini AI for: {candidate.candidate_name}")
                
                messages = [
                    HumanMessage(content=full_prompt)
                ]
                
                response = self.llm.invoke(messages)
                logger.info(f"Received final evaluation response for: {candidate.candidate_name}")
                
                # Parse the response
                response_text = response.content
                logger.info(f"Final evaluation response length: {len(response_text)}")
                
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                logger.info(f"Final evaluation parsed JSON: {json_text[:200]}...")
                
                final_score = parser.parse(json_text)
                final_scores.append(final_score)
                
                logger.info(f"Final evaluation for {final_score.candidate_name}: Score {final_score.final_score:.3f}, Rank {final_score.final_rank}")
                
            except Exception as e:
                logger.error(f"Error in final evaluation for {candidate.candidate_name}: {e}")
                logger.error(f"Full error details: {str(e)}")
                continue
        
        logger.info(f"Successfully completed final evaluation for {len(final_scores)} out of {len(top_candidates)} candidates")
        
        # If no candidates were evaluated by LLM, use fallback evaluation
        if not final_scores:
            logger.warning("LLM evaluation failed for all candidates, using fallback evaluation")
            final_scores = self._fallback_final_evaluation(scored_candidates, top_n)
        
        # Sort by final rank
        init_lookup = {c.candidate_name: c.initial_score for c in scored_candidates}
        final_scores.sort(
            key=lambda s: (s.final_score, init_lookup.get(s.candidate_name, 0.0)),
            reverse=True
        )

        for i, fs in enumerate(final_scores, start=1):
            fs.final_rank = i

        return final_scores


    def process_job_and_rank_candidates(
        self,
        job_description: str,
        top_n: int = DEFAULT_TOP_N,
    ) -> Dict[str, Any]:
        """
        Main method to process a job description and rank candidates.
        Pipeline:
          1) Load + prepare resumes
          2) Categorize JD
          3) Filter resumes by category(ies)
          4) Initial AI scoring
          5) Final LLM evaluation (top N)
          6) Persist JobDescription + CandidateScore rows

        Returns a dict with counts, preview lists, stored_in_db flag and job_id.
        """
        diagnostics: list[str] = []
        job_id: Optional[int] = None

        try:
            logger.info("🚀 Starting comprehensive resume processing and ranking...")

            # -------------------------
            # Step 1: Load + prepare
            # -------------------------
            logger.info("Step 1: Loading resumes from database...")
            df = self._load_resumes_from_db()
            if df is None:
                diagnostics.append("load_resumes: returned None")
                logger.warning("No resumes dataframe returned from DB")
                return {
                    "job_category": None,
                    "filtered_candidates": 0,
                    "initial_scores": [],
                    "final_scores": [],
                    "stored_in_db": False,
                    "job_id": None,
                    "error": "No resumes found in database",
                    "diagnostics": diagnostics,
                }

            logger.info("Step 1a: Preparing resume text...")
            df = self._prepare_resume_text(df)
            total_resumes = len(df)
            diagnostics.append(f"resumes_total={total_resumes}")
            if total_resumes == 0:
                logger.warning("No resumes available after preparation")
                return {
                    "job_category": None,
                    "filtered_candidates": 0,
                    "initial_scores": [],
                    "final_scores": [],
                    "stored_in_db": False,
                    "job_id": None,
                    "error": "No resumes available",
                    "diagnostics": diagnostics,
                }

            # -------------------------
            # Step 2: Categorize JD
            # -------------------------
            job_category = self._categorize_job_description(job_description)
            cats = job_category.all_categories or [job_category.role_category]
            logger.info(
                "✅ Job categorized as: %s (also: %s) Conf: %.2f",
                job_category.role_category,
                ", ".join(job_category.all_categories) if job_category.all_categories else "none",
                job_category.confidence_score,
            )
            diagnostics.append(
                f"role_category={job_category.role_category}, "
                f"all={cats}, conf={job_category.confidence_score:.2f}"
            )

            # -------------------------
            # Step 3: Filter by category(ies)
            # -------------------------
            logger.info("Step 3: Filtering resumes for categories: %s", cats)
            filtered_df = self._filter_resumes_by_categories(df, cats)
            filtered_count = len(filtered_df)
            diagnostics.append(f"filtered_candidates={filtered_count}")

            if filtered_count == 0:
                msg = f"No resumes found for categories: {cats}"
                logger.warning(msg)
                return {
                    "job_category": job_category,
                    "filtered_candidates": 0,
                    "initial_scores": [],
                    "final_scores": [],
                    "stored_in_db": False,
                    "job_id": None,
                    "error": msg,
                    "diagnostics": diagnostics,
                }

            # -------------------------
            # Step 4: Initial AI scoring
            # -------------------------
            logger.info("Step 4: Performing initial AI scoring...")
            initial_scores = self._initial_ai_scoring(filtered_df, job_description) or []
            initial_count = len(initial_scores)
            diagnostics.append(f"initial_scored={initial_count}")

            if initial_count == 0:
                msg = "Initial scoring returned 0 candidates"
                logger.warning(msg)
                return {
                    "job_category": job_category,
                    "filtered_candidates": filtered_count,
                    "initial_scores": [],
                    "final_scores": [],
                    "stored_in_db": False,
                    "job_id": None,
                    "error": msg,
                    "diagnostics": diagnostics,
                }

            # -------------------------
            # Step 5: Final LLM evaluation / ranking
            # -------------------------
            logger.info("Step 5: Performing final LLM evaluation and ranking (top_n=%d)...", int(top_n))
            final_scores = self._final_llm_evaluation(initial_scores, job_description, int(top_n)) or []
            final_count = len(final_scores)
            diagnostics.append(f"final_ranked={final_count}")

            if final_count == 0:
                msg = "Final LLM evaluation returned 0 candidates"
                logger.warning(msg)
                return {
                    "job_category": job_category,
                    "filtered_candidates": filtered_count,
                    "initial_scores": initial_scores,
                    "final_scores": [],
                    "stored_in_db": False,
                    "job_id": None,
                    "error": msg,
                    "diagnostics": diagnostics,
                }

            # -------------------------
            # Step 6: Persist to DB
            # -------------------------
            logger.info("Step 6: Storing results in PostgreSQL database...")
            stored_successfully, job_id = self.db_manager.store_job_results(
                job_description=job_description,
                job_category=job_category,
                final_scores=final_scores,
            )
            diagnostics.append(f"stored_in_db={bool(stored_successfully)}")
            if stored_successfully:
                logger.info("✅ Processing complete! Results stored (job_id=%s)", job_id)
            else:
                logger.warning("⚠️ Processing complete but failed to store results in database")

            # Summary log
            logger.info(
                "Pipeline summary → total=%d, filtered=%d, initial=%d, final=%d",
                total_resumes, filtered_count, initial_count, final_count
            )

            return {
                "job_category": job_category,
                "filtered_candidates": filtered_count,
                "initial_scores": initial_scores,
                "final_scores": final_scores,
                "stored_in_db": bool(stored_successfully),
                "job_id": job_id,
                "error": None if stored_successfully else "Failed to store results in database",
                "diagnostics": diagnostics,
            }

        except Exception as e:
            logger.error("Error during processing: %s", e)
            logger.error("Error type: %s", type(e))
            logger.error("Traceback:\n%s", __import__("traceback").format_exc())
            diagnostics.append(f"exception={e}")
            return {
                "job_category": None,
                "filtered_candidates": 0,
                "initial_scores": [],
                "final_scores": [],
                "stored_in_db": False,
                "job_id": None,
                "error": str(e),
                "diagnostics": diagnostics,
            }
        finally:
            # If your DatabaseManager uses pooled connections, consider removing this close().
            try:
                self.db_manager.close()
            except Exception as e:
                logger.error("Error closing database connection: %s", e)
