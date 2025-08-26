"""
MCP Server for AI-Powered Resume Processor & Ranker using FastMCP

This MCP server provides tools for:
1. Analyzing job descriptions and categorizing them
2. Retrieving resumes from the database based on categories
3. Ranking resumes using AI
4. Storing results back to the database
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

# Initialize database manager and resume processor as None for now
db_manager = None
resume_processor = None

def get_resume_processor():
    """Get or initialize the resume processor."""
    global resume_processor
    if resume_processor is None:
        try:
            # Import here to avoid circular imports
            from ranker_agent import ResumeProcessor
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
            # Import here to avoid circular imports
            from ranker_agent import DatabaseManager
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

class ResumeFilterInput(BaseModel):
    category: str = Field(description="Category to filter resumes by")
    limit: int = Field(default=50, description="Maximum number of resumes to return")

class ResumeRankingInput(BaseModel):
    job_description: str = Field(description="Job description for ranking")
    candidate_names: List[str] = Field(description="List of candidate names to rank")
    top_n: int = Field(default=10, description="Number of top candidates to return")

class DatabaseQueryInput(BaseModel):
    query: str = Field(description="SQL query to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")

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
                "tools": "5 available"
            }
        }
    except Exception as e:
        return {
            "server_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def get_database_stats() -> Dict[str, Any]:
    """Get statistics about the resume database."""
    try:
        db = get_database_manager()
        df = db.get_all_resumes()
        
        return {
            "total_resumes": len(df) if not df.empty else 0,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "message": "Database stats retrieved successfully"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def analyze_job_description(job_description: str, top_n: int = 10) -> Dict[str, Any]:
    """Analyze a job description and automatically categorize it using AI."""
    try:
        processor = get_resume_processor()
        job_category = processor._categorize_job_description(job_description)
        
        return {
            "role_category": job_category.role_category,
            "confidence_score": job_category.confidence_score,
            "reasoning": job_category.reasoning,
            "key_indicators": job_category.key_indicators,
            "top_n": top_n,
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
async def filter_resumes_by_category(category: str, limit: int = 50) -> Dict[str, Any]:
    """Filter resumes by category and return matching candidates."""
    try:
        db = get_database_manager()
        # This would need to be implemented in your DatabaseManager
        # For now, returning a placeholder response
        return {
            "category": category,
            "limit": limit,
            "status": "success",
            "message": f"Filtered resumes for category: {category}",
            "timestamp": datetime.now().isoformat(),
            "note": "Database filtering implementation needed"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def rank_resumes_for_job(job_description: str, candidate_names: List[str], top_n: int = 10) -> Dict[str, Any]:
    """Rank resumes for a specific job description using AI."""
    try:
        processor = get_resume_processor()
        # This would need to be implemented in your ResumeProcessor
        # For now, returning a placeholder response
        return {
            "job_description": job_description[:100] + "..." if len(job_description) > 100 else job_description,
            "candidates_analyzed": len(candidate_names),
            "top_n": top_n,
            "status": "success",
            "message": "Resume ranking completed",
            "timestamp": datetime.now().isoformat(),
            "note": "AI ranking implementation needed"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
async def execute_database_query(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a custom database query."""
    try:
        db = get_database_manager()
        # This would need to be implemented in your DatabaseManager
        # For now, returning a placeholder response
        return {
            "query": query,
            "params": params,
            "status": "success",
            "message": "Query executed successfully",
            "timestamp": datetime.now().isoformat(),
            "note": "Custom query execution implementation needed"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    async def show_tools():
        tools = await mcp.get_tools()
        print(f"Number of tools: {len(tools)}")
        print(f"Tool names: {tools}")

    asyncio.run(show_tools())
    mcp.run(transport="stdio")