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
import sqlite3

import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

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
DB_PATH = os.getenv('DB_PATH', 'jhire_resumes.db')


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
    """Manages SQLite database connections and operations."""
    
    def __init__(self):
        """Initialize database connection."""
        self.connection = None
        self._connect()
        self._initialize_tables()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.connection = sqlite3.connect(DB_PATH)
            logger.info(f"Successfully connected to SQLite database at {DB_PATH}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def _initialize_tables(self):
        """Initialize required tables if they don't exist."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Enable foreign key support for SQLite
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create resumes table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    location VARCHAR(255),
                    category VARCHAR(100),
                    role_category VARCHAR(100),
                    job_category VARCHAR(100),
                    position_type VARCHAR(100),
                    technical_skills TEXT,
                    work_experience TEXT,
                    education TEXT,
                    certifications TEXT,
                    degrees TEXT,
                    projects TEXT,
                    languages TEXT,
                    soft_skills TEXT,
                    achievements TEXT,
                    linkedin_url VARCHAR(500),
                    github_url VARCHAR(500),
                    portfolio_url VARCHAR(500),
                    years_of_experience INTEGER,
                    current_company VARCHAR(255),
                    current_role VARCHAR(255),
                    salary_expectations VARCHAR(100),
                    availability VARCHAR(100),
                    visa_status VARCHAR(100),
                    remote_preference VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create jobdescription table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobdescription (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_description TEXT NOT NULL,
                    role_category VARCHAR(100) NOT NULL,
                    categorization_confidence REAL NOT NULL,
                    categorization_reasoning TEXT NOT NULL,
                    key_indicators TEXT NOT NULL,
                    total_candidates_evaluated INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create candidate_scores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidate_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    candidate_name VARCHAR(255) NOT NULL,
                    final_score REAL NOT NULL,
                    final_rank INTEGER NOT NULL,
                    detailed_reasoning TEXT NOT NULL,
                    strengths TEXT NOT NULL,
                    weaknesses TEXT NOT NULL,
                    recommendation VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobdescription(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumes_category ON resumes(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumes_role_category ON resumes(role_category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_scores_job_id ON candidate_scores(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_scores_candidate_name ON candidate_scores(candidate_name)")
            
            # Check if resumes table has data, if not, insert sample data
            cursor.execute("SELECT COUNT(*) FROM resumes")
            resume_count = cursor.fetchone()[0]
            
            if resume_count == 0:
                logger.info("No resumes found, inserting sample data...")
                self._insert_sample_resumes(cursor)
            
            conn.commit()
            logger.info("Database tables initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database tables: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
    
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
    
    def get_connection(self):
        """Get database connection, reconnect if needed."""
        try:
            if self.connection is None:
                self._connect()
            return self.connection
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def get_all_resumes(self) -> pd.DataFrame:
        """Fetch all resumes from the resumes table."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM resumes"
            cursor.execute(query)
            
            # Fetch all rows and convert to DataFrame
            rows = cursor.fetchall()
            logger.info(f"Fetched {len(rows)} rows from database")
            
            # Get column names
            column_names = [description[0] for description in cursor.description]
            logger.info(f"Column names: {column_names}")
            
            # Create DataFrame with proper column names
            df = pd.DataFrame(rows, columns=column_names)
            logger.info(f"Created DataFrame with shape: {df.shape}")
            
            cursor.close()
            logger.info(f"Loaded {len(df)} resumes from database")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching resumes from database: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def store_job_results(
        self, 
        job_description: str, 
        job_category: JobCategory,
        final_scores: List[FinalScore]
    ) -> bool:
        """Store job analysis results in the jobdescription table."""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Validate inputs
            if not job_description or not job_description.strip():
                raise ValueError("Job description cannot be empty")
            
            if not final_scores:
                logger.warning("No final scores to store")
                return False
            
            # Insert job description and analysis
            job_insert_query = """
            INSERT INTO jobdescription (
                job_description, 
                role_category, 
                categorization_confidence, 
                categorization_reasoning, 
                key_indicators,
                total_candidates_evaluated,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            cursor.execute(job_insert_query, (
                job_description.strip(),
                job_category.role_category,
                job_category.confidence_score,
                job_category.reasoning,
                json.dumps(job_category.key_indicators),
                len(final_scores)
            ))
            
            job_id = cursor.lastrowid
            logger.info(f"Inserted job with ID: {job_id}")
            
            # Insert candidate scores
            candidate_insert_query = """
            INSERT INTO candidate_scores (
                job_id,
                candidate_name,
                final_score,
                final_rank,
                detailed_reasoning,
                strengths,
                weaknesses,
                recommendation,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            for candidate in final_scores:
                cursor.execute(candidate_insert_query, (
                    job_id,
                    candidate.candidate_name,
                    candidate.final_score,
                    candidate.final_rank,
                    candidate.detailed_reasoning,
                    json.dumps(candidate.strengths),
                    json.dumps(candidate.weaknesses),
                    candidate.recommendation
                ))
                logger.info(f"Inserted candidate: {candidate.candidate_name}")
            
            conn.commit()
            logger.info(f"Successfully stored job results in database with job_id: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing job results in database: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()


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
        final_scores.sort(key=lambda x: x.final_rank)
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
