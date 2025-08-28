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

async def run_single_job_example():
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


async def run_interactive_mode():
    """Run the agent in interactive mode."""
    try:
        from mcp_client import EnhancedResumeRankingAgent
        
        agent = EnhancedResumeRankingAgent()
        await agent.interactive_job_processing()
        
    except Exception as e:
        print(f"Interactive mode failed: {str(e)}")


async def run_batch_example():
    """Run batch processing example."""
    try:
        from mcp_client import BatchJobProcessor
        
        processor = BatchJobProcessor()
        
        # Example batch jobs
        example_jobs = [
            {
                "title": "Senior Data Scientist",
                "description": """
                Senior Data Scientist position requiring ML expertise, Python proficiency,
                and experience with statistical modeling. Must have 5+ years experience
                in data science with strong background in deep learning and NLP.
                """,
                "top_n": 3
            },
            {
                "title": "Full Stack Developer", 
                "description": """
                Full Stack Developer role using React, Node.js, and PostgreSQL.
                Looking for 2+ years experience with modern web development,
                API design, and cloud deployment experience.
                """,
                "top_n": 4
            }
        ]
        
        print("Running batch processing example...")
        batch_results = await processor.process_job_batch(example_jobs)
        
        # Generate and display report
        report = processor.generate_batch_report(batch_results)
        print("\n" + report)
        
    except Exception as e:
        print(f"Batch processing failed: {str(e)}")


def main():
    """Main function with menu options."""
    print("AI Resume Ranking Agent")
    print("=" * 40)
    print("1. Process single job description")
    print("2. Interactive mode")
    print("3. Batch processing example")
    print("4. Exit")
    
    while True:
        try:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                asyncio.run(run_single_job_example())
            elif choice == "2":
                asyncio.run(run_interactive_mode())
            elif choice == "3":
                asyncio.run(run_batch_example())
            elif choice == "4":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please select 1-4.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("Error: GOOGLE_API_KEY environment variable not set!")
        print("Please add GOOGLE_API_KEY=your_api_key_here to your .env file")
        exit(1)
    
    main()