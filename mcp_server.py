"""
MCP Server for AI-Powered Resume Processor & Ranker using FastMCP

This MCP server provides comprehensive tools for:
1. Analyzing and categorizing job descriptions using AI
2. Filtering resumes from database based on categories
3. Initial AI scoring of candidates
4. Final LLM-based ranking and detailed evaluation
5. Database operations and statistics
6. Complete end-to-end job processing workflow
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Windows Unicode compatibility fix
def safe_print(text):
    """Print text safely, handling Unicode encoding issues on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        import re
        clean_text = re.sub(r'[^\x00-\x7F]+', '', text)
        print(clean_text)

# Fix Windows console encoding
if sys.platform.startswith('win'):
    try:
        import os
        os.system('chcp 65001 >nul 2>&1')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except:
        pass


# Initialize global components
db_manager = None
resume_processor = None

def get_resume_processor():
    """Get or initialize the resume processor."""
    global resume_processor
    if resume_processor is None:
        try:
            from mcp_tools import ResumeProcessor
            resume_processor = ResumeProcessor()
            logger.info("Resume processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize resume processor: {e}")
            raise
    return resume_processor

def get_database_manager():
    """Get or initialize the database manager."""
    global db_manager
    if db_manager is None:
        try:
            from mcp_tools import DatabaseManager
            db_manager = DatabaseManager()
            logger.info("Database manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
    return db_manager

# Pydantic models for MCP tool inputs/outputs
class JobDescriptionInput(BaseModel):
    job_description: str = Field(description="The job description to analyze and categorize")
    top_n: int = Field(default=10, description="Number of top candidates to return")

class JobCategorizationInput(BaseModel):
    job_description: str = Field(description="The job description to categorize")

class ResumeFilterInput(BaseModel):
    category: str = Field(description="Category to filter resumes by (data_science, data_engineering, full_stack, platform_engineering, consulting, software_engineering, product_management, ui_ux_design)")
    limit: int = Field(default=50, description="Maximum number of resumes to return")

class InitialScoringInput(BaseModel):
    job_description: str = Field(description="Job description for scoring")
    category: str = Field(description="Category to filter candidates by")
    limit: int = Field(default=20, description="Maximum number of candidates to score")

class FinalRankingInput(BaseModel):
    job_description: str = Field(description="Job description for final ranking")
    candidate_names: List[str] = Field(description="List of candidate names to rank")
    top_n: int = Field(default=10, description="Number of top candidates to return")

class DatabaseQueryInput(BaseModel):
    query: str = Field(description="SQL query to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")

class StoreResultsInput(BaseModel):
    job_description: str = Field(description="The original job description")
    job_category_data: Dict[str, Any] = Field(description="Job category analysis results")
    final_scores_data: List[Dict[str, Any]] = Field(description="Final candidate scores and rankings")

# Create FastMCP server instance
mcp = FastMCP("resume-ranker-server")

# Tool definitions using FastMCP

@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """Check the health and status of the MCP server and its components."""
    try:
        # Try to initialize components
        db_status = "not_initialized"
        ai_status = "not_initialized"
        
        try:
            get_database_manager()
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        try:
            get_resume_processor()
            ai_status = "healthy"
        except Exception as e:
            ai_status = f"unhealthy: {str(e)}"
        
        return {
            "server_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "server": "healthy",
                "database": db_status,
                "ai_model": ai_status,
                "tools": "8 available"
            },
            "available_tools": [
                "health_check",
                "get_database_stats", 
                "analyze_job_description",
                "filter_resumes_by_category",
                "initial_score_candidates",
                "final_rank_candidates",
                "process_complete_job",
                "store_job_results"
            ]
        }
    except Exception as e:
        return {
            "server_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def get_database_stats() -> Dict[str, Any]:
    """Get comprehensive statistics about the resume database."""
    try:
        db = get_database_manager()
        df = db.get_all_resumes()
        
        stats = {
            "total_resumes": len(df) if not df.empty else 0,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        
        if not df.empty:
            # Add more detailed stats
            stats.update({
                "columns": df.columns.tolist(),
                "sample_candidate_names": df.get('full_name', df.get('name', pd.Series())).head(3).tolist(),
                "database_shape": df.shape,
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
            })
        
        return stats
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def analyze_job_description(job_description: str) -> Dict[str, Any]:
    """Analyze a job description and automatically categorize it using AI."""
    try:
        processor = get_resume_processor()
        job_category = processor._categorize_job_description(job_description)
        
        return {
            "role_category": job_category.role_category,
            "confidence_score": job_category.confidence_score,
            "reasoning": job_category.reasoning,
            "key_indicators": job_category.key_indicators,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "available_categories": [
                "data_science", "data_engineering", "full_stack", 
                "platform_engineering", "consulting", "software_engineering",
                "product_management", "ui_ux_design"
            ]
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def filter_resumes_by_category(category: str, limit: int = 50) -> Dict[str, Any]:
    """Filter resumes by category and return matching candidates."""
    try:
        processor = get_resume_processor()
        db = get_database_manager()
        
        # Load all resumes
        df = db.get_all_resumes()
        if df.empty:
            return {
                "error": "No resumes found in database",
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
        
        # Filter by category
        filtered_df = processor._filter_resumes_by_category(df, category)
        
        # Prepare response with limited results
        candidates = []
        for idx, row in filtered_df.head(limit).iterrows():
            candidate_name = row.get('full_name', row.get('name', row.get('candidate_name', 'Unknown')))
            candidates.append({
                "name": candidate_name,
                "category": category,
                "id": row.get('id', idx)
            })
        
        return {
            "category": category,
            "total_matches": len(filtered_df),
            "returned_candidates": len(candidates),
            "limit": limit,
            "candidates": candidates,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def initial_score_candidates(job_description: str, category: str, limit: int = 20) -> Dict[str, Any]:
    """Perform initial AI scoring of candidates for a job description."""
    try:
        processor = get_resume_processor()
        db = get_database_manager()
        
        # Load and filter resumes
        df = db.get_all_resumes()
        if df.empty:
            return {
                "error": "No resumes found in database",
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
        
        # Prepare resume text
        df = processor._prepare_resume_text(df)
        
        # Filter by category
        filtered_df = processor._filter_resumes_by_category(df, category)
        
        if filtered_df.empty:
            return {
                "error": f"No candidates found for category: {category}",
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
        
        # Perform initial scoring
        initial_scores = processor._initial_ai_scoring(filtered_df.head(limit), job_description)
        
        # Convert to serializable format
        scores_data = []
        for score in initial_scores:
            scores_data.append({
                "candidate_name": score.candidate_name,
                "initial_score": score.initial_score,
                "key_matches": score.key_matches,
                "areas_of_concern": score.areas_of_concern
            })
        
        return {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "category": category,
            "candidates_scored": len(scores_data),
            "initial_scores": scores_data,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def final_rank_candidates(job_description: str, initial_scores_data: List[Dict[str, Any]], top_n: int = 10) -> Dict[str, Any]:
    """Perform final LLM-based ranking and detailed evaluation of candidates."""
    try:
        processor = get_resume_processor()
        
        # Convert initial scores data back to InitialScore objects
        from mcp_tools import InitialScore
        initial_scores = []
        for score_data in initial_scores_data:
            initial_scores.append(InitialScore(
                candidate_name=score_data["candidate_name"],
                initial_score=score_data["initial_score"],
                key_matches=score_data["key_matches"],
                areas_of_concern=score_data["areas_of_concern"]
            ))
        
        # Perform final ranking using the correct method name
        final_scores = processor._final_llm_evaluation(initial_scores, job_description, top_n)
        
        # Convert to serializable format
        final_scores_data = []
        for score in final_scores:
            final_scores_data.append({
                "candidate_name": score.candidate_name,
                "final_score": score.final_score,
                "final_rank": score.final_rank,
                "detailed_reasoning": score.detailed_reasoning,
                "strengths": score.strengths,
                "weaknesses": score.weaknesses,
                "recommendation": score.recommendation
            })
        
        return {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "candidates_ranked": len(final_scores_data),
            "top_n": top_n,
            "final_rankings": final_scores_data,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def process_complete_job(job_description: str, top_n: int = 10) -> Dict[str, Any]:
    """Complete end-to-end job processing: categorization, filtering, scoring, ranking, and storage."""
    try:
        processor = get_resume_processor()
        
        # Process the complete job
        results = processor.process_job_and_rank_candidates(
            job_description=job_description,
            top_n=top_n
        )
        
        # Convert results to serializable format
        response = {
            "job_description_preview": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        
        if results.get('job_category'):
            response["job_category"] = {
                "role_category": results['job_category'].role_category,
                "confidence_score": results['job_category'].confidence_score,
                "reasoning": results['job_category'].reasoning,
                "key_indicators": results['job_category'].key_indicators
            }
        
        response.update({
            "filtered_candidates": results.get('filtered_candidates', 0),
            "stored_in_db": results.get('stored_in_db', False)
        })
        
        # Convert initial scores
        if results.get('initial_scores'):
            response["initial_scores"] = [
                {
                    "candidate_name": score.candidate_name,
                    "initial_score": score.initial_score,
                    "key_matches": score.key_matches,
                    "areas_of_concern": score.areas_of_concern
                }
                for score in results['initial_scores']
            ]
        
        # Convert final scores
        if results.get('final_scores'):
            response["final_rankings"] = [
                {
                    "candidate_name": score.candidate_name,
                    "final_score": score.final_score,
                    "final_rank": score.final_rank,
                    "detailed_reasoning": score.detailed_reasoning,
                    "strengths": score.strengths,
                    "weaknesses": score.weaknesses,
                    "recommendation": score.recommendation
                }
                for score in results['final_scores']
            ]
        
        # Include any errors
        if results.get('error'):
            response["warning"] = results['error']
        
        return response
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def store_job_results(job_description: str, job_category_data: Dict[str, Any], final_scores_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Store job analysis results in the database."""
    try:
        db = get_database_manager()
        
        # Convert job_category_data back to JobCategory object
        from mcp_tools import JobCategory, FinalScore
        job_category = JobCategory(
            role_category=job_category_data["role_category"],
            confidence_score=job_category_data["confidence_score"],
            reasoning=job_category_data["reasoning"],
            key_indicators=job_category_data["key_indicators"]
        )
        
        # Convert final_scores_data back to FinalScore objects
        final_scores = []
        for score_data in final_scores_data:
            final_scores.append(FinalScore(
                candidate_name=score_data["candidate_name"],
                final_score=score_data["final_score"],
                final_rank=score_data["final_rank"],
                detailed_reasoning=score_data["detailed_reasoning"],
                strengths=score_data["strengths"],
                weaknesses=score_data["weaknesses"],
                recommendation=score_data["recommendation"]
            ))
        
        # Store results
        success = db.store_job_results(job_description, job_category, final_scores)
        
        return {
            "stored_successfully": success,
            "job_category": job_category_data["role_category"],
            "candidates_stored": len(final_scores_data),
            "status": "success" if success else "error",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def execute_database_query(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a custom database query for advanced operations."""
    try:
        db = get_database_manager()
        conn = db.get_connection()
        
        # Execute query safely
        if params:
            cursor = conn.execute(query, params)
        else:
            cursor = conn.execute(query)
        
        # Handle different types of queries
        if query.strip().upper().startswith('SELECT'):
            # For SELECT queries, return results
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            # Convert to list of dictionaries
            data = []
            for row in results:
                data.append(dict(zip(columns, row)))
            
            return {
                "query": query,
                "results_count": len(data),
                "data": data[:100],  # Limit to first 100 rows
                "columns": columns,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # For other queries (INSERT, UPDATE, DELETE), return row count
            rowcount = cursor.rowcount
            conn.commit()
            
            return {
                "query": query,
                "rows_affected": rowcount,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def get_job_history(limit: int = 10) -> Dict[str, Any]:
    """Get history of processed jobs from the database."""
    try:
        query = """
        SELECT 
            id, 
            job_description,
            role_category,
            categorization_confidence,
            total_candidates_evaluated,
            created_at
        FROM jobdescription 
        ORDER BY created_at DESC 
        LIMIT ?
        """
        
        result = await execute_database_query(query, {"limit": limit})
        
        if result["status"] == "success":
            return {
                "job_history": result["data"],
                "total_jobs": result["results_count"],
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
            
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def get_candidate_rankings(job_id: int) -> Dict[str, Any]:
    """Get candidate rankings for a specific job."""
    try:
        query = """
        SELECT 
            candidate_name,
            final_score,
            final_rank,
            detailed_reasoning,
            strengths,
            weaknesses,
            recommendation,
            created_at
        FROM candidate_scores 
        WHERE job_id = ?
        ORDER BY final_rank
        """
        
        result = await execute_database_query(query, {"job_id": job_id})
        
        if result["status"] == "success":
            # Parse JSON fields
            for candidate in result["data"]:
                try:
                    candidate["strengths"] = json.loads(candidate["strengths"]) if candidate["strengths"] else []
                    candidate["weaknesses"] = json.loads(candidate["weaknesses"]) if candidate["weaknesses"] else []
                except json.JSONDecodeError:
                    candidate["strengths"] = [candidate["strengths"]] if candidate["strengths"] else []
                    candidate["weaknesses"] = [candidate["weaknesses"]] if candidate["weaknesses"] else []
            
            return {
                "job_id": job_id,
                "candidates": result["data"],
                "total_candidates": result["results_count"],
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
            
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    print("Resume Ranker MCP Server - Starting...")
    mcp.run(transport="stdio")