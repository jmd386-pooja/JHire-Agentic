"""
Simple Usage Script for Resume Ranking Agent

This script provides a simple interface to run the AI agent
that processes job descriptions and ranks resumes using the MCP server.
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_agent():
    """Run a single job processing example."""
    try:
        # Import the agent (assuming real MCP implementation)
        from mcp_client import EnhancedResumeRankingAgent
        
        print("Initializing AI Resume Ranking Agent...")
        agent = EnhancedResumeRankingAgent()
        
        # Example job description
        job_description = input("""Enter your job description:""").strip()
        
        if not job_description:
            # Use default example
            job_description = """
                Senior Machine Learning Engineer
        
                We are looking for an experienced ML Engineer to join our AI team.

                Requirements:
                - 3+ years experience in machine learning and deep learning
                - Strong proficiency in Python, TensorFlow, PyTorch
                - Experience with MLOps, model deployment, and monitoring
                - Knowledge of computer vision and NLP
                - Experience with cloud platforms (AWS, GCP)
                - Strong mathematical background in statistics and linear algebra

                Responsibilities:
                - Design and implement ML models for production
                - Optimize model performance and scalability
                - Collaborate with data scientists and engineers
                - Build ML infrastructure and pipelines
            """
        
        try:
            top_n = int(input("Number of top candidates to find (default 5): ") or "5")
        except ValueError:
            top_n = 5
        
        print(f"\nProcessing job for top {top_n} candidates...")
        print("-" * 80)
        
        # Process the job
        results = await agent.process_job_with_workflow_tracking(job_description, top_n)
        
        # Display comprehensive results
        display_comprehensive_results(results)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure your MCP server is properly configured and running.")


def display_comprehensive_results(results):
    """Display comprehensive results in a user-friendly format."""
    print("\n" + "="*80)
    print("RESUME RANKING RESULTS")
    print("="*80)
    
    if not results.get("success"):
        print(f"PROCESSING FAILED")
        print(f"Error: {results.get('error', 'Unknown error')}")
        
        if results.get("workflow_log"):
            print("\nExecution Log:")
            for log in results["workflow_log"]:
                print(f"  • {log}")
        return
    
    # Main results
    print(f"Status: SUCCESS")
    print(f"Job Category: {results.get('job_category', 'Unknown')}")
    print(f"Total Candidates Evaluated: {results.get('total_filtered', 0)}")
    print(f"Results Stored in Database: {'Yes' if results.get('stored_in_database') else 'No'}")
    print(f"Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Top candidates section
    top_candidates = results.get("top_candidates", [])
    if top_candidates:
        print(f"\n{'='*20} TOP {len(top_candidates)} CANDIDATES {'='*20}")
        
        for candidate in top_candidates:
            name = candidate.get("candidate_name", "Unknown")
            score = candidate.get("final_score", 0)
            rank = candidate.get("final_rank", 0)
            recommendation = candidate.get("recommendation", "Unknown")
            strengths = candidate.get("strengths", [])
            weaknesses = candidate.get("weaknesses", [])
            reasoning = candidate.get("detailed_reasoning", "")
            
            print(f"\nRANK {rank}: {name}")
            print(f"Final Score: {score:.3f}/1.000")
            print(f"Recommendation: {recommendation}")
            
            if strengths:
                print(f"Key Strengths: {', '.join(strengths[:3])}")
            if weaknesses:
                print(f"Areas for Improvement: {', '.join(weaknesses[:2])}")
            
            if reasoning and len(reasoning) > 0:
                print(f"Reasoning: {reasoning[:200]}{'...' if len(reasoning) > 200 else ''}")
            
            print("-" * 60)
    
    # AI Summary
    ai_summary = results.get("ai_summary")
    if ai_summary:
        print(f"\n{'='*20} AI ANALYSIS SUMMARY {'='*20}")
        print(ai_summary)
    
    # Database storage details
    print(f"\n{'='*20} DATABASE STORAGE DETAILS {'='*20}")
    if results.get("stored_in_database"):
        print("✓ Job analysis and rankings successfully stored")
        print("✓ Results are available for future reference")
        print("✓ Can be retrieved using job history tools")
    else:
        print("✗ Failed to store results in database")
        print("  Check database connection and permissions")
    
    # Execution workflow
    workflow_log = results.get("workflow_log", [])
    if workflow_log:
        print(f"\n{'='*20} EXECUTION WORKFLOW {'='*20}")
        for i, step in enumerate(workflow_log, 1):
            status_indicator = "✓" if "success" in step.lower() or "completed" in step.lower() else "•"
            print(f"{status_indicator} Step {i}: {step}")
    
    print("\n" + "="*80)



def main():
    """Main function with menu options."""
    print("AI Resume Ranking Agent")
    try:
        asyncio.run(run_agent())
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("Error: GOOGLE_API_KEY environment variable not set!")
        print("Please add GOOGLE_API_KEY=your_api_key_here to your .env file")
        exit(1)
    
    main()