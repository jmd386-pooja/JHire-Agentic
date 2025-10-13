"""
MCP Client for Resume Ranking Agent

This module provides the actual MCP client implementation to connect
with the resume ranking MCP server and execute tools.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import os
import sys, subprocess, shutil
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Minimal, stable MCP stdio client used by agents to call tools on the MCP server.
    This __init__ only prepares StdioServerParameters; your higher-level code
    should use these params to start/connect to the MCP server.
    """

    def __init__(
        self,
        server_script_path: str = "ai/mcp_server.py",
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        # Resolve paths
        self.server_script_path = str(Path(server_script_path).resolve())
        self.cwd = str(Path(cwd).resolve()) if cwd else str(Path(self.server_script_path).parent)

        # Compose environment (inherit + overrides)
        base_env = os.environ.copy()
        if env:
            base_env.update(env)

        # Ensure PYTHONPATH contains project root so `ai/*` imports work inside the server
        base_env["PYTHONPATH"] = os.pathsep.join(
            p for p in [self.cwd, base_env.get("PYTHONPATH", "")] if p
        )
        self.env = base_env

        # Prepare stdio server params (let the MCP client library spawn the process)
        self.server_params = StdioServerParameters(
            command=sys.executable,          # use the current interpreter
            args=[self.server_script_path],  # script to run
            env=self.env,                    # pass through env (contains DB creds, API keys, etc.)
            cwd=self.cwd,                    # run from project dir so relative imports/files work
        )

    # ---------- core async API ----------

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as sess:
                await sess.initialize()
                res = await sess.call_tool(name, arguments)
                # Standard JSON payload comes back in the first content item as .text
                if getattr(res, "content", None):
                    item = res.content[0]
                    text = getattr(item, "text", str(item))
                    try:
                        return json.loads(text)
                    except Exception:
                        # Fallback to raw text if tool returned plain text
                        return {"status": "success", "result": text}
                return {"status": "success", "result": ""}

    async def execute_database_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"query": query}
        if params:
            args["params"] = params
        return await self.call_tool("execute_database_query", args)

    async def db_info(self) -> Dict[str, Any]:
        return await self.call_tool("db_info", {})

    async def health_check(self) -> Dict[str, Any]:
        return await self.call_tool("health_check", {})

    # ---------- optional sync helpers (nice for quick scripts) ----------

    def call_tool_sync(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return asyncio.run(self.call_tool(name, arguments))

    def execute_database_query_sync(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return asyncio.run(self.execute_database_query(query, params))

    def db_info_sync(self) -> Dict[str, Any]:
        return asyncio.run(self.db_info())

    def health_check_sync(self) -> Dict[str, Any]:
        return asyncio.run(self.health_check())


# Backward-compat alias (some modules used MCPDB earlier)
MCPDB = MCPClient

__all__ = ["MCPClient", "MCPDB"]



class MCPResumeRankingClient:
    """
    MCP Client for connecting to the Resume Ranking MCP Server.
    """
    
    def __init__(self, server_script_path: str = "mcp_server.py"):
        """Initialize MCP client."""
        self.server_script_path = server_script_path
        self.session = None
    
    @asynccontextmanager
    async def get_session(self):
        """Get an MCP session context manager."""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script_path]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call an MCP tool and return the result.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as a dictionary
            
        Returns:
            Tool result as a dictionary
        """
        try:
            async with self.get_session() as session:
                # Call the tool
                result = await session.call_tool(tool_name, arguments or {})
                
                # Handle different result types
                if hasattr(result, 'content'):
                    # Handle TextContent and other content types
                    if hasattr(result.content[0], 'text'):
                        result_text = result.content[0].text
                        try:
                            return json.loads(result_text)
                        except json.JSONDecodeError:
                            return {"result": result_text, "status": "success"}
                    else:
                        return {"result": str(result.content[0]), "status": "success"}
                else:
                    return {"result": str(result), "status": "success"}
                    
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return {
                "error": str(e),
                "status": "error",
                "tool_name": tool_name,
                "arguments": arguments
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MCP server health."""
        return await self.call_tool("health_check")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return await self.call_tool("get_database_stats")
    
    async def analyze_job_description(self, job_description: str) -> Dict[str, Any]:
        """Analyze and categorize job description."""
        return await self.call_tool("analyze_job_description", {
            "job_description": job_description
        })
    
    async def filter_resumes_by_category(self, category: str, limit: int = 50) -> Dict[str, Any]:
        """Filter resumes by category."""
        return await self.call_tool("filter_resumes_by_category", {
            "category": category,
            "limit": limit
        })
    
    async def initial_score_candidates(self, job_description: str, category: str, limit: int = 20) -> Dict[str, Any]:
        """Perform initial scoring of candidates."""
        return await self.call_tool("initial_score_candidates", {
            "job_description": job_description,
            "category": category,
            "limit": limit
        })
    
    async def final_rank_candidates(self, job_description: str, initial_scores_data: List[Dict[str, Any]], top_n: int = 10) -> Dict[str, Any]:
        """Perform final ranking of candidates."""
        return await self.call_tool("final_rank_candidates", {
            "job_description": job_description,
            "initial_scores_data": initial_scores_data,
            "top_n": top_n
        })
    
    async def process_complete_job(self, job_description: str, top_n: int = 10) -> Dict[str, Any]:
        """Process complete job workflow."""
        return await self.call_tool("process_complete_job", {
            "job_description": job_description,
            "top_n": top_n
        })
    
    async def store_job_results(self, job_description: str, job_category_data: Dict[str, Any], final_scores_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Store job results in database."""
        return await self.call_tool("store_job_results", {
            "job_description": job_description,
            "job_category_data": job_category_data,
            "final_scores_data": final_scores_data
        })
    
    async def get_job_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get job processing history."""
        return await self.call_tool("get_job_history", {
            "limit": limit
        })
    
    async def get_candidate_rankings(self, job_id: int) -> Dict[str, Any]:
        """Get candidate rankings for a specific job."""
        return await self.call_tool("get_candidate_rankings", {
            "job_id": job_id
        })


# Enhanced Resume Ranking Agent with Real MCP Integration
class EnhancedResumeRankingAgent:
    """
    Enhanced AI Agent that uses actual MCP client to interact with the server.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp"):
        """Initialize the enhanced agent."""
        self.model_name = model_name
        self.mcp_client = MCPResumeRankingClient()
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize Gemini AI model."""
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not found.")
            
            from langchain_google_genai import ChatGoogleGenerativeAI
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=0.1,
                google_api_key=api_key,
                convert_system_message_to_human=True
            )
            logger.info(f"Initialized Gemini AI model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI model: {e}")
            raise
    
    async def process_job_with_workflow_tracking(self, job_description: str, top_n: int = 10) -> Dict[str, Any]:
        """
        Process job with detailed workflow tracking and intelligent decision making.
        """
        workflow_log = []
        results = {}
        
        try:
            # Step 1: Health Check
            workflow_log.append("Starting system health check...")
            health_result = await self.mcp_client.health_check()
            workflow_log.append(f"Health check: {health_result.get('status', 'unknown')}")
            
            if health_result.get("status") == "error":
                return {
                    "success": False,
                    "error": "System health check failed",
                    "workflow_log": workflow_log,
                    "health_result": health_result
                }
            
            # Step 2: Database Statistics
            workflow_log.append("Checking database statistics...")
            db_stats = await self.mcp_client.get_database_stats()
            workflow_log.append(f"Database contains {db_stats.get('total_resumes', 0)} resumes")
            results["database_stats"] = db_stats
            
            # Step 3: Job Description Analysis
            workflow_log.append("Analyzing job description with AI...")
            job_analysis = await self.mcp_client.analyze_job_description(job_description)
            
            if job_analysis.get("status") == "error":
                workflow_log.append(f"Job analysis failed: {job_analysis.get('error')}")
                return {
                    "success": False,
                    "error": "Job analysis failed",
                    "workflow_log": workflow_log
                }
            
            category = job_analysis.get("role_category", "unknown")
            confidence = job_analysis.get("confidence_score", 0)
            workflow_log.append(f"Job categorized as: {category} (confidence: {confidence:.2f})")
            results["job_analysis"] = job_analysis
            
            # Step 4: Complete Job Processing
            workflow_log.append("Starting complete job processing workflow...")
            complete_result = await self.mcp_client.process_complete_job(job_description, top_n)
            
            if complete_result.get("status") == "error":
                workflow_log.append(f"Complete processing failed: {complete_result.get('error')}")
                return {
                    "success": False,
                    "error": "Complete job processing failed",
                    "workflow_log": workflow_log,
                    "partial_results": results
                }
            
            # Extract results
            filtered_count = complete_result.get("filtered_candidates", 0)
            final_rankings = complete_result.get("final_rankings", [])
            stored_in_db = complete_result.get("stored_in_db", False)
            
            workflow_log.append(f"Filtered {filtered_count} relevant candidates")
            workflow_log.append(f"Ranked top {len(final_rankings)} candidates")
            workflow_log.append(f"Results stored in database: {'Yes' if stored_in_db else 'No'}")
            
            results["complete_processing"] = complete_result
            
            # Step 5: Generate AI Summary and Insights
            workflow_log.append("Generating AI insights and recommendations...")
            ai_summary = await self._generate_processing_summary(
                job_description, complete_result, workflow_log
            )
            results["ai_summary"] = ai_summary
            
            # Success!
            workflow_log.append("Processing completed successfully!")
            
            return {
                "success": True,
                "workflow_log": workflow_log,
                "results": results,
                "top_candidates": final_rankings[:top_n] if final_rankings else [],
                "job_category": category,
                "total_filtered": filtered_count,
                "stored_in_database": stored_in_db,
                "ai_summary": ai_summary
            }
            
        except Exception as e:
            workflow_log.append(f"Critical error occurred: {str(e)}")
            logger.error(f"Error in workflow processing: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "workflow_log": workflow_log,
                "partial_results": results
            }
    
    async def _generate_processing_summary(self, job_description: str, processing_results: Dict[str, Any], workflow_log: List[str]) -> str:
        """Generate AI summary of the processing results."""
        try:
            # Extract key information
            job_category = processing_results.get("job_category", {})
            final_rankings = processing_results.get("final_rankings", [])
            
            summary_prompt = f"""
            You are an expert HR analyst. Provide a comprehensive summary of the resume ranking process.
            
            JOB DESCRIPTION:
            {job_description[:300]}...
            
            PROCESSING RESULTS:
            - Job Category: {job_category.get('role_category', 'unknown')}
            - Confidence: {job_category.get('confidence_score', 0):.2f}
            - Candidates Filtered: {processing_results.get('filtered_candidates', 0)}
            - Top Candidates Ranked: {len(final_rankings)}
            - Stored in DB: {processing_results.get('stored_in_db', False)}
            
            TOP CANDIDATES:
            {json.dumps(final_rankings[:3], indent=2) if final_rankings else "None"}
            
            WORKFLOW LOG:
            {chr(10).join(workflow_log)}
            
            Provide a professional summary that includes:
            1. Job analysis summary
            2. Candidate pool insights
            3. Top recommendations with reasoning
            4. Database storage confirmation
            5. Next steps for the hiring manager
            
            Keep it concise but comprehensive.
            """
            
            from langchain.schema import HumanMessage
            messages = [HumanMessage(content=summary_prompt)]
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return f"Summary generation failed: {str(e)}"
    
    async def interactive_job_processing(self):
        """Interactive mode for processing jobs."""
        print("\n" + "="*80)
        print("INTERACTIVE RESUME RANKING AGENT")
        print("="*80)
        print("This agent will help you process job descriptions and rank candidates.")
        print("Type 'quit' to exit.\n")
        
        while True:
            try:
                # Get job description from user
                print("-" * 40)
                job_description = input("Enter job description (or 'quit' to exit): ").strip()
                
                if job_description.lower() == 'quit':
                    print("Goodbye!")
                    break
                
                if not job_description:
                    print("Please enter a valid job description.")
                    continue
                
                # Get top_n preference
                try:
                    top_n_input = input("How many top candidates do you want? (default: 5): ").strip()
                    top_n = int(top_n_input) if top_n_input else 5
                except ValueError:
                    top_n = 5
                
                print(f"\nProcessing job description for top {top_n} candidates...")
                
                # Process the job
                results = await self.process_job_with_workflow_tracking(job_description, top_n)
                
                # Display results
                self._display_processing_results(results)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
                logger.error(f"Interactive processing error: {e}")
    
    def _display_processing_results(self, results: Dict[str, Any]):
        """Display processing results in a user-friendly format."""
        print("\n" + "="*60)
        print("PROCESSING RESULTS")
        print("="*60)
        
        if not results.get("success"):
            print(f"ERROR: {results.get('error', 'Unknown error')}")
            if results.get("workflow_log"):
                print("\nWorkflow Log:")
                for log_entry in results["workflow_log"]:
                    print(f"  - {log_entry}")
            return
        
        # Success case
        print(f"Status: SUCCESS")
        print(f"Job Category: {results.get('job_category', 'Unknown')}")
        print(f"Candidates Filtered: {results.get('total_filtered', 0)}")
        print(f"Stored in Database: {'Yes' if results.get('stored_in_database') else 'No'}")
        
        # Top candidates
        top_candidates = results.get("top_candidates", [])
        if top_candidates:
            print(f"\nTOP {len(top_candidates)} CANDIDATES:")
            print("-" * 40)
            
            for candidate in top_candidates:
                name = candidate.get("candidate_name", "Unknown")
                score = candidate.get("final_score", 0)
                rank = candidate.get("final_rank", 0)
                recommendation = candidate.get("recommendation", "Unknown")
                strengths = candidate.get("strengths", [])
                
                print(f"{rank}. {name}")
                print(f"   Score: {score:.3f}")
                print(f"   Recommendation: {recommendation}")
                print(f"   Key Strengths: {', '.join(strengths[:3])}")
                print()
        
        # AI Summary
        ai_summary = results.get("ai_summary")
        if ai_summary:
            print("AI ANALYSIS SUMMARY:")
            print("-" * 40)
            print(ai_summary)
        
        # Workflow log
        workflow_log = results.get("workflow_log", [])
        if workflow_log:
            print("\nWORKFLOW EXECUTION LOG:")
            print("-" * 40)
            for i, log_entry in enumerate(workflow_log, 1):
                print(f"{i}. {log_entry}")
        
        print("\n" + "="*60)


class BatchJobProcessor:
    """
    Batch processor for handling multiple job descriptions.
    """
    
    def __init__(self):
        """Initialize batch processor."""
        self.agent = EnhancedResumeRankingAgent()
        self.processed_jobs = []
    
    async def process_job_batch(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple jobs in batch.
        
        Args:
            jobs: List of job dictionaries with 'description' and optional 'top_n'
            
        Returns:
            List of processing results
        """
        batch_results = []
        
        print(f"Processing {len(jobs)} jobs in batch...")
        
        for i, job in enumerate(jobs, 1):
            try:
                print(f"\nProcessing job {i}/{len(jobs)}...")
                
                job_description = job.get("description", "")
                top_n = job.get("top_n", 10)
                job_title = job.get("title", f"Job {i}")
                
                if not job_description:
                    batch_results.append({
                        "job_title": job_title,
                        "success": False,
                        "error": "No job description provided"
                    })
                    continue
                
                # Process the job
                result = await self.agent.process_job_with_workflow_tracking(job_description, top_n)
                result["job_title"] = job_title
                result["job_index"] = i
                
                batch_results.append(result)
                
                # Add delay between jobs to avoid overwhelming the system
                if i < len(jobs):
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error processing job {i}: {e}")
                batch_results.append({
                    "job_title": job.get("title", f"Job {i}"),
                    "job_index": i,
                    "success": False,
                    "error": str(e)
                })
        
        return batch_results
    
    def generate_batch_report(self, batch_results: List[Dict[str, Any]]) -> str:
        """Generate a comprehensive batch processing report."""
        successful = sum(1 for result in batch_results if result.get("success"))
        failed = len(batch_results) - successful
        
        report = [
            "BATCH PROCESSING REPORT",
            "=" * 50,
            f"Total jobs processed: {len(batch_results)}",
            f"Successful: {successful}",
            f"Failed: {failed}",
            f"Success rate: {(successful/len(batch_results)*100):.1f}%",
            ""
        ]
        
        # Successful jobs summary
        if successful > 0:
            report.append("SUCCESSFUL JOBS:")
            report.append("-" * 30)
            
            for result in batch_results:
                if result.get("success"):
                    title = result.get("job_title", "Unknown")
                    category = result.get("job_category", "Unknown")
                    candidates = len(result.get("top_candidates", []))
                    report.append(f"• {title}: {category} category, {candidates} top candidates")
            report.append("")
        
        # Failed jobs
        if failed > 0:
            report.append("FAILED JOBS:")
            report.append("-" * 30)
            
            for result in batch_results:
                if not result.get("success"):
                    title = result.get("job_title", "Unknown")
                    error = result.get("error", "Unknown error")
                    report.append(f"• {title}: {error}")
        
        return "\n".join(report)

