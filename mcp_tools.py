"""
AI-Powered Resume Processor & Ranker

This system analyzes a single job description, automatically categorizes the role,
filters relevant resumes from SQLite database, performs AI-powered ranking, and then uses LLM for
final perfect scoring with detailed reasoning. Results are stored back to SQLite.
"""

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
DEFAULT_MODEL_NAME = "gemini-2.5-flash-lite"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TOP_N = 10

# Database configuration
PG_DSN = os.getenv('DATABASE_URL')

def pg_conn():
    if not PG_DSN:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(PG_DSN)


class JobCategory(BaseModel):
    """Pydantic model for job category classification."""
    role_category: str = Field(description="The main role category")
    confidence_score: float = Field(description="Confidence in the classification from 0.0 to 1.0")
    reasoning: str = Field(description="Explanation of why this category was chosen")
    key_indicators: List[str] = Field(description="Key terms/phrases that indicate this category")


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
        Create required tables and the 'resumes' compatibility view if they don't exist.
        Works whether your Prisma tables are CamelCase ("Candidate") or lowercase (candidate).
        """
        log = logging.getLogger(__name__)
        if self.connection is None or getattr(self.connection, "closed", True):
            self._connect()
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # ---------- Required app tables ----------
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.jobdescription (
                      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      job_description            TEXT        NOT NULL,
                      role_category              TEXT        NOT NULL,
                      categorization_confidence  DOUBLE PRECISION NOT NULL,
                      categorization_reasoning   TEXT        NOT NULL,
                      key_indicators             JSONB       NOT NULL,
                      total_candidates_evaluated INTEGER     NOT NULL,
                      created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
                      updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.candidate_scores (
                      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      job_id           BIGINT REFERENCES public.jobdescription(id) ON DELETE CASCADE,
                      candidate_name   TEXT      NOT NULL,
                      resume_email     TEXT,
                      final_score      DOUBLE PRECISION NOT NULL,
                      final_rank       INTEGER   NOT NULL,
                      detailed_reasoning TEXT    NOT NULL,
                      strengths        JSONB     NOT NULL,
                      weaknesses       JSONB     NOT NULL,
                      recommendation   TEXT      NOT NULL,
                      created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                      updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.exam_credentials (
                      candidate_email TEXT PRIMARY KEY,
                      username        TEXT NOT NULL,
                      password        TEXT NOT NULL,
                      exam_link       TEXT NOT NULL,
                      created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.email_audit (
                      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

                # ---------- Detect Prisma table casing ----------
                def tbl_exists(name: str) -> bool:
                    cur.execute("""
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema='public' AND table_name=%s
                        LIMIT 1
                    """, (name,))
                    return cur.fetchone() is not None

                has_camel = tbl_exists("Candidate") and tbl_exists("Category") and tbl_exists("ResumeDetails")
                has_lower = tbl_exists("candidate") and tbl_exists("category") and tbl_exists("resume_details")

                # ---------- Create/replace the resumes view ----------
                if has_camel:
                    create_view_sql = """
                    CREATE OR REPLACE VIEW public.resumes AS
                    SELECT
                      -- Candidate (all columns, clearly prefixed)
                      c.id                          AS candidate_id,
                      c."name"                      AS candidate_name,
                      c."email"                     AS candidate_email,
                      c."status"                    AS candidate_status,
                      c."createdAt"                 AS candidate_created_at,
                      c."updatedAt"                 AS candidate_updated_at,
                      c."Avatar"                    AS candidate_avatar,
                      c."Skills"                    AS candidate_skills,       -- TEXT[]
                      c."Voice"                     AS candidate_voice,
                      c."ph_number"                 AS candidate_ph_number,
                      c."Exam_URL"                  AS candidate_exam_url,
                      c."tempPassword"              AS candidate_temp_password,
                      c."temp_name"                 AS candidate_temp_name,
                      c."College"                   AS candidate_college,
                      c."Exam_date"                 AS candidate_exam_date,
                      c."Expiry"                    AS candidate_expiry,
                    
                      -- ResumeDetails (all columns, prefixed; alias colliding names)
                      rd.id                         AS resume_id,
                      rd."candidateId"              AS resume_candidate_id,
                      rd."name"                     AS resume_name,
                      rd."email"                    AS resume_email,
                      rd."phone"                    AS resume_phone,
                      rd."skills"                   AS resume_skills,          -- TEXT[]
                      rd."UG_college"               AS resume_ug_college,
                      rd."UG_cgpa"                  AS resume_ug_cgpa,
                      rd."UG_yop"                   AS resume_ug_yop,
                      rd."PG_college"               AS resume_pg_college,
                      rd."PG_cgpa"                  AS resume_pg_cgpa,
                      rd."PG_yop"                   AS resume_pg_yop,
                      rd."projects"                 AS resume_projects,        -- TEXT[]
                      rd."certifications"           AS resume_certifications,  -- TEXT[]
                      rd."experience"               AS resume_experience,      -- TEXT[]
                      rd."fileName"                 AS resume_file_name,
                      rd."processedAt"              AS resume_processed_at,
                    
                      -- Category (aggregated because it's 1-to-many)
                      ARRAY_AGG(DISTINCT cat.id)                     FILTER (WHERE cat.id IS NOT NULL)         AS category_ids,
                      ARRAY_AGG(DISTINCT cat."type")                 FILTER (WHERE cat."type" IS NOT NULL)     AS category_types,
                      ARRAY_AGG(cat."createdAt")                     FILTER (WHERE cat."createdAt" IS NOT NULL)AS category_created_at,
                    
                      -- Back-compat / convenience columns your code already uses
                      COALESCE(array_to_string(rd."skills",         ' '), '') AS technical_skills,
                      COALESCE(array_to_string(rd."experience",     ' '), '') AS work_experience,
                      COALESCE(array_to_string(rd."projects",       ' '), '') AS projects,
                      COALESCE(array_to_string(rd."certifications", ' '), '') AS certifications,
                      COALESCE(rd."UG_college", '')                         AS education,
                      COALESCE(string_agg(DISTINCT cat."type", ' '), '')    AS category,      -- single text field
                      c."name"                                              AS full_name,     -- legacy alias
                      c."email"                                             AS email          -- legacy alias
                    FROM "Candidate"       AS c
                    LEFT JOIN "ResumeDetails"   AS rd  ON rd."candidateId" = c.id
                    LEFT JOIN "Category"        AS cat ON cat."candidateId" = c.id
                    GROUP BY
                      c.id, c."name", c."email", c."status", c."createdAt", c."updatedAt",
                      c."Avatar", c."Skills", c."Voice", c."ph_number", c."Exam_URL",
                      c."tempPassword", c."temp_name", c."College", c."Exam_date", c."Expiry",
                      rd.id, rd."candidateId", rd."name", rd."email", rd."phone", rd."skills",
                      rd."UG_college", rd."UG_cgpa", rd."UG_yop",
                      rd."PG_college", rd."PG_cgpa", rd."PG_yop",
                      rd."projects", rd."certifications", rd."experience",
                      rd."fileName", rd."processedAt";
                    
                    """
                elif has_lower:
                    create_view_sql = """
                    CREATE OR REPLACE VIEW public.resumes AS
                    SELECT
                      -- candidate
                      c.id                  AS candidate_id,
                      c.name                AS candidate_name,
                      c.email               AS candidate_email,
                      c.status              AS candidate_status,
                      c.created_at          AS candidate_created_at,
                      c.updated_at          AS candidate_updated_at,
                      c.avatar              AS candidate_avatar,
                      c.skills              AS candidate_skills,        -- TEXT[]
                      c.voice               AS candidate_voice,
                      c.ph_number           AS candidate_ph_number,
                      c.exam_url            AS candidate_exam_url,
                      c.temp_password       AS candidate_temp_password,
                      c.temp_name           AS candidate_temp_name,
                      c.college             AS candidate_college,
                      c.exam_date           AS candidate_exam_date,
                      c.expiry              AS candidate_expiry,

                      -- resume_details
                      rd.id                 AS resume_id,
                      rd.candidate_id       AS resume_candidate_id,
                      rd.name               AS resume_name,
                      rd.email              AS resume_email,
                      rd.phone              AS resume_phone,
                      rd.skills             AS resume_skills,           -- TEXT[]
                      rd.ug_college         AS resume_ug_college,
                      rd.ug_cgpa            AS resume_ug_cgpa,
                      rd.ug_yop             AS resume_ug_yop,
                      rd.pg_college         AS resume_pg_college,
                      rd.pg_cgpa            AS resume_pg_cgpa,
                      rd.pg_yop             AS resume_pg_yop,
                      rd.projects           AS resume_projects,         -- TEXT[]
                      rd.certifications     AS resume_certifications,   -- TEXT[]
                      rd.experience         AS resume_experience,       -- TEXT[]
                      rd.file_name          AS resume_file_name,
                      rd.processed_at       AS resume_processed_at,

                      -- category aggregated
                      ARRAY_AGG(DISTINCT cat.id)            FILTER (WHERE cat.id IS NOT NULL)      AS category_ids,
                      ARRAY_AGG(DISTINCT cat.type)          FILTER (WHERE cat.type IS NOT NULL)    AS category_types,
                      ARRAY_AGG(cat.created_at)             FILTER (WHERE cat.created_at IS NOT NULL) AS category_created_at,

                      -- back-compat fields used by your agents
                      COALESCE(array_to_string(rd.skills,         ' '), '') AS technical_skills,
                      COALESCE(array_to_string(rd.experience,     ' '), '') AS work_experience,
                      COALESCE(array_to_string(rd.projects,       ' '), '') AS projects,
                      COALESCE(array_to_string(rd.certifications, ' '), '') AS certifications,
                      COALESCE(rd.ug_college, '')                       AS education,
                      COALESCE(string_agg(DISTINCT cat.type, ' '), '')  AS category,
                      c.name                                           AS full_name,
                      c.email                                          AS email
                    FROM candidate c
                    LEFT JOIN resume_details rd ON rd.candidate_id = c.id
                    LEFT JOIN category       cat ON cat.candidate_id = c.id
                    GROUP BY
                      c.id, c.name, c.email, c.status, c.created_at, c.updated_at,
                      c.avatar, c.skills, c.voice, c.ph_number, c.exam_url,
                      c.temp_password, c.temp_name, c.college, c.exam_date, c.expiry,
                      rd.id, rd.candidate_id, rd.name, rd.email, rd.phone, rd.skills,
                      rd.ug_college, rd.ug_cgpa, rd.ug_yop,
                      rd.pg_college, rd.pg_cgpa, rd.pg_yop,
                      rd.projects, rd.certifications, rd.experience,
                      rd.file_name, rd.processed_at;

                    """
                else:
                    create_view_sql = None
                    log.warning("Prisma tables not found (Candidate/Category/ResumeDetails). Skipping view creation.")

                if create_view_sql:
                    cur.execute(create_view_sql)

            conn.commit()
            log.info("Schema ensured (tables + resumes view ready).")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            log.error("ensure_schema failed: %s", e, exc_info=True)
            raise
        
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
        # NEW: be defensive – if the view didn’t exist yet, create and retry once
        try:
            with self.get_connection().cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT * FROM public.resumes")
                rows = cur.fetchall()
            return pd.DataFrame(rows)
        except psycopg.errors.UndefinedTable:
            self.ensure_schema_once()
            with self.get_connection().cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT * FROM public.resumes")
                rows = cur.fetchall()
            return pd.DataFrame(rows)
    
    def store_job_results(self, job_description: str, job_category: JobCategory, final_scores: List[FinalScore],) -> bool:
        """
        Store one job description row and all of its candidate scores in PostgreSQL.
        Returns True on success, False on any error.
        """
    
        # Basic validation up front
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty")
        if not final_scores:
            logger.warning("No final scores to store")
            return False
        self.ensure_schema()
        conn = self.get_connection()  # must return a psycopg.Connection
        try:
            with conn.cursor() as cur:
                # 1) Insert the jobdescription row and get its id
                cur.execute(
                    """
                    INSERT INTO jobdescription (
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
                        job_description.strip(),
                        job_category.role_category,
                        float(job_category.confidence_score),
                        job_category.reasoning,
                        json.dumps(getattr(job_category, "key_indicators", [])),
                        len(final_scores),
                    ),
                )
                job_id = cur.fetchone()[0]
                logger.info("Inserted jobdescription id=%s", job_id)
    
                # 2) Insert all candidate scores for this job
                insert_score_sql = """
                    INSERT INTO candidate_scores (
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
                    cur.execute(
                        insert_score_sql,
                        (
                            job_id,
                            s.candidate_name,
                            None,  # or an email if you have it at this stage
                            float(s.final_score),
                            int(s.final_rank),
                            s.detailed_reasoning,
                            json.dumps(getattr(s, "strengths", [])),
                            json.dumps(getattr(s, "weaknesses", [])),
                            s.recommendation,
                        ),
                    )
                    logger.info("Inserted candidate score for %s", s.candidate_name)
    
            # 3) Commit once after all inserts succeed
            conn.commit()
            logger.info(
                "Successfully stored job %s with %d candidate scores",
                job_id,
                len(final_scores),
            )
            return True
    
        except Exception as e:
            logger.error("Error storing job results: %s", e, exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
    

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
        """Combine ALL columns from resume table into structured text format for AI processing."""
        df = df.copy()
        
        combined_texts = []
        for _, row in df.iterrows():
            text_parts = []
            
            # Add candidate name if it exists
            name = row.get('full_name', row.get('name', row.get('candidate_name', 'Unknown')))
            text_parts.append(f"CANDIDATE: {name}")
            
            # Concatenate ALL columns (excluding the name column we already added)
            for column in df.columns:
                if column.lower() not in ['full_name', 'name', 'candidate_name', 'id']:
                    value = row.get(column, '')
                    if pd.notna(value) and str(value).strip():
                        # Convert all values to string and clean them
                        clean_value = str(value).strip()
                        if clean_value and clean_value.lower() not in ['nan', 'none', 'null']:
                            text_parts.append(f"{column.upper()}: {clean_value}")
            
            combined_texts.append('\n'.join(text_parts))
        
        df['combined_text'] = combined_texts
        return df
    
    def _categorize_job_description(self, job_description: str) -> JobCategory:
        """Use AI to automatically categorize the job description."""
        try:
            prompt = f"""
            You are an expert HR professional and technical recruiter. Your task is to analyze a job description and determine the primary role category.

            JOB DESCRIPTION:
            {job_description}

            Please classify this job into one of these categories:
            - data_science: Machine learning, data analysis, statistical modeling, AI/ML
            - data_engineering: Data pipelines, ETL/ELT, big data technologies, data infrastructure
            - full_stack: Front-end and back-end development, web applications, full software stack
            - platform_engineering: Infrastructure, DevOps, cloud platforms, system architecture
            - consulting: Business consulting, strategy, advisory services, client-facing roles
            - software_engineering: General software development, programming, software architecture
            - product_management: Product strategy, roadmap, stakeholder management, market analysis
            - ui_ux_design: User interface design, user experience, visual design, prototyping

            Provide your classification with confidence and reasoning.
            """
            
            # Create output parser
            parser = PydanticOutputParser(pydantic_object=JobCategory)
            format_instructions = parser.get_format_instructions()
            full_prompt = f"{prompt}\n\n{format_instructions}"
            
            # Get AI response - use only HumanMessage
            messages = [
                HumanMessage(content=full_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Parse the response
            response_text = response.content
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text
            
            return parser.parse(json_text)
            
        except Exception as e:
            logger.error(f"Error categorizing job description: {e}")
            return self._fallback_categorization(job_description)
    
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
        """Filter resumes by the identified job category."""
        # Look for category column in various possible names
        category_columns = ['category', 'role_category', 'job_category', 'position_type']
        category_col = None
        
        for col in category_columns:
            if col in df.columns:
                category_col = col
                break
        
        if not category_col:
            logger.warning("No category column found in resume data, processing all resumes")
            return df
        
        # Map internal categories to resume categories
        category_mapping = {
            'data_science': ['data science', 'data scientist', 'ml engineer', 'ai engineer'],
            'data_engineering': ['data engineer', 'data engineering', 'etl developer'],
            'full_stack': ['full stack', 'fullstack', 'web developer', 'software developer'],
            'platform_engineering': ['platform engineer', 'devops engineer', 'infrastructure engineer'],
            'consulting': ['consultant', 'consulting', 'advisor', 'strategist'],
            'software_engineering': ['software engineer', 'developer', 'programmer'],
            'product_management': ['product manager', 'product owner', 'program manager'],
            'ui_ux_design': ['ui designer', 'ux designer', 'designer', 'visual designer']
        }
        
        target_categories = category_mapping.get(category, [category])
        
        # Filter resumes
        filtered_df = df[df[category_col].str.lower().str.contains(
            '|'.join(target_categories), na=False, case=False
        )]
        
        logger.info(f"Found {len(filtered_df)} candidates in category '{category}'")
        return filtered_df
    
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
        top_n: int = DEFAULT_TOP_N
    ) -> Dict[str, Any]:
        """Main method to process a job description and rank candidates."""
        try:
            logger.info("🚀 Starting comprehensive resume processing and ranking...")
            
            # Step 1: Load and prepare resumes from PostgreSQL
            logger.info("Step 1: Loading resumes from database...")
            df = self._load_resumes_from_db()
            logger.info("Step 1a: Preparing resume text...")
            df = self._prepare_resume_text(df)
            
            # Step 2: Categorize the job description
            logger.info("Step 2: Analyzing job description to determine category...")
            job_category = self._categorize_job_description(job_description)
            logger.info(f"✅ Job categorized as: {job_category.role_category} (Confidence: {job_category.confidence_score:.2f})")
            
            # Step 3: Filter resumes by category
            logger.info(f"Step 3: Filtering resumes for category: {job_category.role_category}")
            filtered_df = self._filter_resumes_by_category(df, job_category.role_category)
            
            if filtered_df.empty:
                logger.warning(f"No resumes found for category: {job_category.role_category}")
                return {
                    'job_category': job_category,
                    'filtered_candidates': 0,
                    'initial_scores': [],
                    'final_scores': [],
                    'stored_in_db': False,
                    'error': f"No resumes found for category: {job_category.role_category}"
                }
            
            # Step 4: Initial AI scoring
            logger.info("Step 4: Performing initial AI scoring...")
            initial_scores = self._initial_ai_scoring(filtered_df, job_description)
            
            if not initial_scores:
                logger.warning("No candidates were successfully scored in initial phase")
                return {
                    'job_category': job_category,
                    'filtered_candidates': len(filtered_df),
                    'initial_scores': [],
                    'final_scores': [],
                    'stored_in_db': False,
                    'error': "AI scoring failed for all candidates"
                }
            
            # Step 5: Final LLM evaluation and ranking
            logger.info("Step 5: Performing final LLM evaluation and perfect ranking...")
            final_scores = self._final_llm_evaluation(initial_scores, job_description, top_n)
            
            if not final_scores:
                logger.warning("Final LLM evaluation failed for all candidates")
                return {
                    'job_category': job_category,
                    'filtered_candidates': len(filtered_df),
                    'initial_scores': initial_scores,
                    'final_scores': [],
                    'stored_in_db': False,
                    'error': "Final LLM evaluation failed for all candidates"
                }
            
            # Step 6: Store results in SQLite
            logger.info("Step 6: Storing results in SQLite database...")
            stored_successfully = self.db_manager.store_job_results(job_description, job_category, final_scores)
            
            if stored_successfully:
                logger.info(f"✅ Processing complete! Results stored in database successfully")
            else:
                logger.warning("⚠️ Processing complete but failed to store results in database")
            
            return {
                'job_category': job_category,
                'filtered_candidates': len(filtered_df),
                'initial_scores': initial_scores,
                'final_scores': final_scores,
                'stored_in_db': stored_successfully,
                'error': None if stored_successfully else "Failed to store results in database"
            }
            
        except Exception as e:
            logger.error(f"Error during processing: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'job_category': None,
                'filtered_candidates': 0,
                'initial_scores': [],
                'final_scores': [],
                'stored_in_db': False,
                'error': str(e)
            }
        finally:
            # Close database connection
            try:
                self.db_manager.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
