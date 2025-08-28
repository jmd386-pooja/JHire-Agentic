"""
Conversational Resume Ranking Agent using Real MCP Server

This agent provides conversational interface that connects to the actual MCP server
and uses real tools for job processing, database queries, and candidate ranking.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferWindowMemory
from langchain.pydantic_v1 import BaseModel, Field

# MCP Client imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP client not installed. Please install: pip install mcp")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConversationState:
    """Manages conversation state and context for the MCP-powered agent."""
    
    def __init__(self):
        self.current_job_results = None
        self.recent_jobs = []
        self.last_rankings = []
        self.conversation_history = []
        self.database_stats = None
        self.last_job_id = None
    
    def add_job_result(self, job_description: str, results: Dict[str, Any]):
        """Add new job processing results to state."""
        self.current_job_results = {
            'job_description': job_description,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
        if results.get('final_rankings'):
            self.last_rankings = results['final_rankings']
        
        # Keep last 5 jobs in memory
        self.recent_jobs.append(self.current_job_results)
        if len(self.recent_jobs) > 5:
            self.recent_jobs.pop(0)
    
    def get_current_job_context(self) -> str:
        """Get context about current job for AI responses."""
        if not self.current_job_results:
            return "No job has been processed yet in this conversation."
        
        job_desc = self.current_job_results['job_description'][:100] + "..."
        results = self.current_job_results['results']
        
        context = f"Last processed job: {job_desc}\n"
        if results.get('job_category'):
            job_cat = results['job_category']
            context += f"Category: {job_cat.get('role_category', 'Unknown')}\n"
            context += f"Candidates found: {results.get('filtered_candidates', 0)}\n"
            context += f"Top candidates ranked: {len(results.get('final_rankings', []))}\n"
        
        return context
    
    def find_candidate_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a candidate from last rankings by name."""
        if not self.last_rankings:
            return None
        
        name_lower = name.lower()
        for candidate in self.last_rankings:
            candidate_name = candidate.get('candidate_name', '').lower()
            if name_lower in candidate_name or candidate_name in name_lower:
                return candidate
        return None


class MCPResumeRankingClient:
    """
    Real MCP Client for connecting to the Resume Ranking MCP Server.
    """
    
    def __init__(self, server_script_path: str = "mcp_server.py"):
        """Initialize MCP client."""
        self.server_script_path = server_script_path
        self.session = None
    
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
            # Configure server parameters
            server_params = StdioServerParameters(
                command="python",
                args=[self.server_script_path]
            )
            
            # Create session and call tool
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(tool_name, arguments or {})
                    
                    # Handle different result types
                    if hasattr(result, 'content') and result.content:
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


class ConversationalResumeAgent:
    """
    Conversational AI Agent using Real MCP Server Tools.
    
    This agent connects to the actual MCP server and provides conversational
    interface for job processing and follow-up questions.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp"):
        """Initialize the conversational agent with real MCP connection."""
        self.model_name = model_name
        self.llm = None
        self.mcp_client = MCPResumeRankingClient()
        self.agent_executor = None
        self.conversation_state = ConversationState()
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10
        )
        self._initialize_llm()
        self._create_agent()
    
    def _initialize_llm(self):
        """Initialize the LangChain LLM with Gemini AI."""
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not found.")
            
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
    
    def _create_langchain_tools(self):
        """Create LangChain tools that use real MCP server functionality."""
        tools = []
        
        # Health check tool
        async def health_check_func() -> str:
            """Check the health status of the resume ranking system."""
            try:
                result = await self.mcp_client.call_tool("health_check")
                if result.get("status") != "error":
                    server_status = result.get('server_status', 'unknown')
                    components = result.get('components', {})
                    return f"System is healthy. Server status: {server_status}. All {len(components)} components operational."
                else:
                    return f"System health check failed: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Health check failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=health_check_func,
            name="health_check",
            description="Check the health and status of the resume ranking system"
        ))
        
        # Database statistics tool
        async def get_database_stats_func() -> str:
            """Get comprehensive statistics about the resume database."""
            try:
                result = await self.mcp_client.call_tool("get_database_stats")
                if result.get("status") != "error":
                    total = result.get("total_resumes", 0)
                    sample_names = result.get("sample_candidate_names", [])
                    columns = result.get("columns", [])
                    
                    # Update conversation state
                    self.conversation_state.database_stats = result
                    
                    return f"Database contains {total} resumes with {len(columns)} fields per candidate. Sample candidates: {', '.join(sample_names[:3])}. Database is healthy and accessible."
                else:
                    return f"Failed to get database stats: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Database stats failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=get_database_stats_func,
            name="get_database_stats",
            description="Get comprehensive statistics about the resume database including total resumes and sample data"
        ))
        
        # Job analysis tool
        async def analyze_job_func(job_description: str) -> str:
            """Analyze and categorize a job description using AI."""
            try:
                result = await self.mcp_client.call_tool("analyze_job_description", {
                    "job_description": job_description
                })
                if result.get("status") != "error":
                    category = result.get("role_category", "unknown")
                    confidence = result.get("confidence_score", 0)
                    reasoning = result.get("reasoning", "")
                    key_indicators = result.get("key_indicators", [])
                    return f"Job categorized as: {category} (confidence: {confidence:.2f}). Reasoning: {reasoning}. Key indicators: {', '.join(key_indicators)}"
                else:
                    return f"Job analysis failed: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Job analysis failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=analyze_job_func,
            name="analyze_job_description",
            description="Analyze and categorize a job description to determine the role type"
        ))
        
        # Complete job processing tool
        async def process_complete_job_func(job_description: str, top_n: int = 10) -> str:
            """Process a complete job from description to final rankings and storage."""
            try:
                result = await self.mcp_client.call_tool("process_complete_job", {
                    "job_description": job_description,
                    "top_n": top_n
                })
                
                if result.get("status") != "error":
                    # Update conversation state with results
                    self.conversation_state.add_job_result(job_description, result)
                    
                    job_category = result.get("job_category", {})
                    category_name = job_category.get("role_category", "unknown")
                    filtered_count = result.get("filtered_candidates", 0)
                    final_rankings = result.get("final_rankings", [])
                    stored = result.get("stored_in_db", False)
                    
                    response_parts = [
                        f"Job processed successfully and stored in database!",
                        f"Category: {category_name}",
                        f"Candidates evaluated: {filtered_count}",
                        f"Top ranked candidates: {len(final_rankings)}"
                    ]
                    
                    if final_rankings:
                        response_parts.append("\nTop candidates:")
                        for candidate in final_rankings[:3]:
                            name = candidate.get("candidate_name", "Unknown")
                            score = candidate.get("final_score", 0)
                            rank = candidate.get("final_rank", 0)
                            recommendation = candidate.get("recommendation", "Unknown")
                            response_parts.append(f"  {rank}. {name} (Score: {score:.3f}) - {recommendation}")
                    
                    return "\n".join(response_parts)
                else:
                    return f"Job processing failed: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Complete job processing failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=process_complete_job_func,
            name="process_complete_job",
            description="Process a complete job from analysis to final candidate rankings and database storage"
        ))
        
        # Job history tool
        async def get_job_history_func(limit: int = 10) -> str:
            """Get history of processed jobs from the database."""
            try:
                result = await self.mcp_client.call_tool("get_job_history", {"limit": limit})
                
                if result.get("status") != "error":
                    jobs = result.get("job_history", [])
                    total_jobs = result.get("total_jobs", 0)
                    
                    response = f"Found {len(jobs)} recent jobs (total: {total_jobs} in database):\n\n"
                    
                    for job in jobs:
                        response += f"• Job ID {job.get('id')}: {job.get('role_category', 'Unknown')} role\n"
                        response += f"  Description: {job.get('job_description', '')[:100]}...\n"
                        response += f"  Candidates evaluated: {job.get('total_candidates_evaluated', 0)}\n"
                        response += f"  Date: {job.get('created_at', '')}\n\n"
                    
                    return response
                else:
                    return f"Failed to get job history: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Job history lookup failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=get_job_history_func,
            name="get_job_history",
            description="Get history of previously processed jobs with details from the database"
        ))
        
        # Candidate rankings tool
        async def get_candidate_rankings_func(job_id: int) -> str:
            """Get candidate rankings for a specific job from the database."""
            try:
                result = await self.mcp_client.call_tool("get_candidate_rankings", {"job_id": job_id})
                
                if result.get("status") != "error":
                    candidates = result.get("candidates", [])
                    total_candidates = result.get("total_candidates", 0)
                    
                    response = f"Rankings for Job ID {job_id} ({total_candidates} candidates):\n\n"
                    
                    for candidate in candidates:
                        name = candidate.get("candidate_name", "Unknown")
                        score = candidate.get("final_score", 0)
                        rank = candidate.get("final_rank", 0)
                        reasoning = candidate.get("detailed_reasoning", "")
                        strengths = candidate.get("strengths", [])
                        weaknesses = candidate.get("weaknesses", [])
                        
                        response += f"Rank {rank}: {name} (Score: {score:.3f})\n"
                        if reasoning:
                            response += f"Reasoning: {reasoning}\n"
                        if strengths:
                            response += f"Strengths: {', '.join(strengths[:3])}\n"
                        if weaknesses:
                            response += f"Areas for improvement: {', '.join(weaknesses[:2])}\n"
                        response += f"Recommendation: {candidate.get('recommendation', 'Unknown')}\n\n"
                    
                    return response
                else:
                    return f"Failed to get candidate rankings: {result.get('error', 'unknown error')}"
            except Exception as e:
                return f"Candidate rankings lookup failed: {str(e)}"
        
        tools.append(StructuredTool.from_function(
            func=get_candidate_rankings_func,
            name="get_candidate_rankings",
            description="Get detailed candidate rankings and reasoning for a specific job ID from database"
        ))
        
        return tools
    
    def _create_agent(self):
        """Create the conversational agent with real MCP tools."""
        tools = self._create_langchain_tools()
        
        system_prompt = """
        You are an expert AI Resume Ranking Assistant with access to a real resume database and ranking system through MCP server tools.

        Your capabilities include:
        - Processing job descriptions and ranking candidates using real AI analysis
        - Querying the actual resume database for statistics and information
        - Explaining ranking decisions with detailed reasoning from the database
        - Answering questions about candidates, their qualifications, and rankings
        - Maintaining conversation context across multiple interactions
        - Accessing job history and candidate data from the persistent database

        CONVERSATION GUIDELINES:
        1. Be conversational and helpful - maintain natural dialogue flow
        2. Remember context from previous interactions in the conversation
        3. When given job descriptions, use the complete job processing workflow
        4. Answer follow-up questions using appropriate database tools
        5. Explain reasoning behind rankings when asked "why"
        6. Reference specific candidates and their details when discussed

        TOOL USAGE STRATEGY:
        - Use process_complete_job for any job descriptions provided
        - Use get_database_stats when asked about database content or numbers
        - Use get_job_history when asked about previous jobs processed
        - Use get_candidate_rankings when asked about specific job results
        - Use health_check if there are system issues
        - Always use real database data, never make up information

        RESPONSE STYLE:
        - Be natural and conversational, not robotic
        - Provide specific examples and details from the actual database
        - Explain technical concepts clearly
        - Maintain professional but friendly tone
        - Ask clarifying questions when needed
        - Reference previous conversation context naturally

        You have access to real database information through MCP server tools. Always use these tools to get current, accurate information rather than making assumptions.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=15,
            return_intermediate_steps=True
        )
        
        logger.info("Conversational agent created successfully with real MCP tools")
    
    async def chat(self, user_input: str) -> str:
        """
        Main chat interface for conversational interactions.
        
        Args:
            user_input: User's message/question
            
        Returns:
            AI response as string
        """
        try:
            # Add current context to the input for better responses
            context = self.conversation_state.get_current_job_context()
            
            # Enhanced input with context
            enhanced_input = f"Context from previous interactions: {context}\n\nUser message: {user_input}"
            
            # Execute the agent
            result = await self._execute_agent_async(enhanced_input)
            
            # Extract the response
            response = result.get("output", "I apologize, but I encountered an issue processing your request.")
            
            # Update conversation state
            self.conversation_state.conversation_history.append({
                'user': user_input,
                'assistant': response,
                'timestamp': datetime.now().isoformat()
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"I encountered an error: {str(e)}. The MCP server might not be accessible. Please make sure mcp_server.py is working correctly."
    
    async def _execute_agent_async(self, input_text: str) -> Dict[str, Any]:
        """Execute agent in async context."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.agent_executor.invoke,
                {"input": input_text}
            )
            return result
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the current conversation session."""
        summary = f"Conversation Session Summary:\n"
        summary += f"Jobs processed: {len(self.conversation_state.recent_jobs)}\n"
        summary += f"Messages exchanged: {len(self.conversation_state.conversation_history)}\n"
        
        if self.conversation_state.current_job_results:
            current_job = self.conversation_state.current_job_results
            job_category = current_job['results'].get('job_category', {})
            summary += f"Last job category: {job_category.get('role_category', 'Unknown')}\n"
            summary += f"Last rankings: {len(self.conversation_state.last_rankings)} candidates\n"
        
        return summary


async def start_conversational_interface():
    """Start the conversational interface using real MCP server."""
    print("\n" + "="*80)
    print("AI RESUME RANKING ASSISTANT (Real MCP Server)")
    print("="*80)
    print("I'm your AI assistant powered by the actual resume ranking MCP server.")
    print("\nCapabilities:")
    print("• Process job descriptions → AI analysis → candidate ranking → database storage")
    print("• Answer questions about database content and statistics")
    print("• Explain ranking decisions and candidate details") 
    print("• Access job history and previous processing results")
    print("• Maintain conversation context for natural follow-up questions")
    print("\nExamples of what you can ask:")
    print('• "What\'s in the database?"')
    print('• [Paste job description] → "Process this job"')
    print('• "Why was [candidate name] ranked #1?"')
    print('• "Show me the job history"')
    print('• "Tell me about the person ranked #2"')
    print("\nType 'quit', 'exit', or 'bye' to end the conversation.")
    print("Type 'summary' to see conversation statistics.")
    print("-" * 80)
    
    # Initialize the agent
    try:
        print("Initializing AI agent and connecting to MCP server...")
        agent = ConversationalResumeAgent()
        print("✓ Connected successfully to MCP server!")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        print("Make sure mcp_server.py is accessible and your GOOGLE_API_KEY is set.")
        return
    
    conversation_count = 0
    
    while True:
        try:
            # Get user input
            user_input = input(f"\n[{conversation_count}] You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print("\nAssistant: Thank you for using the AI Resume Ranking Assistant! Your session data has been processed and stored. Goodbye!")
                break
            
            if user_input.lower() == 'summary':
                print(f"\nAssistant: {agent.get_conversation_summary()}")
                continue
            
            if not user_input:
                print("Assistant: I'm here to help! You can give me job descriptions to process, or ask questions about our database and previous rankings.")
                continue
            
            # Get AI response using real MCP tools
            print("\nAssistant: ", end="", flush=True)
            response = await agent.chat(user_input)
            print(response)
            
            conversation_count += 1
            
        except KeyboardInterrupt:
            print("\n\nAssistant: Conversation interrupted. Your session data has been saved. Goodbye!")
            break
        except Exception as e:
            print(f"\nAssistant: I encountered an error: {str(e)}. This might be a connection issue with the MCP server. Let's continue our conversation.")
            logger.error(f"Interface error: {e}")


def main():
    """Main function with real MCP server integration."""
    # Check environment
    if not os.getenv('GOOGLE_API_KEY'):
        print("Error: GOOGLE_API_KEY environment variable not set!")
        print("Please add GOOGLE_API_KEY=your_api_key_here to your .env file")
        return
    
    # Check if MCP server file exists
    if not Path("mcp_server.py").exists():
        print("Error: mcp_server.py not found!")
        print("Make sure the MCP server file is in the same directory.")
        return
    
    print("AI Resume Ranking Assistant with Real MCP Server")
    print("=" * 50)
    print("This agent connects to your actual MCP server and uses real database operations.")
    print("\nStarting conversational interface...")
    
    # Run the conversational interface
    try:
        asyncio.run(start_conversational_interface())
    except Exception as e:
        print(f"Failed to start interface: {e}")
        logger.error(f"Main interface error: {e}")


if __name__ == "__main__":
    main()