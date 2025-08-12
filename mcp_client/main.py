from mcp.server.fastmcp import FastMCP
from typing import List
import random

# Create MCP server
mcp = FastMCP("ResumeInterviewer")

# Resume context (mock data)
resume_context = {
    "skills": ["React.js", "Flask", "FastAPI", "Python", "TypeScript", "LangChain", "GPT APIs", "Pinecone", "Redis", "MongoDB", "Docker", "Azure Functions", "Airflow"],
    "certifications": ["LangChain Bootcamp - LLM Stack", "OpenAI API Developer Certification"],
    "experience": ["Full Stack Engineer at Capgemini (2020 - Present)", "Software Engineer at Zensar (2018 – 2020)"],
    "projects": ["Resume Screening Tool with LLMs", "E-learning Portal with AI Tutor"]
}

# Track what categories have already been asked
asked_topics = set()
interview_history = []
question_count = 0
MAX_QUESTIONS = 12  # Between 10-15

# JD-aligned additional topics to be asked
jd_topics = [
    "Object Oriented Programming concepts",
    "Data Structures and Algorithms",
    "Academic projects or internships",
    "Version control systems like Git",
    "Basics of web technologies like HTML/CSS/JS",
    "Databases you've worked with",
    "Communication and teamwork experience",
    "Familiarity with frameworks like React, Node.js, or Django",
    "Cloud technologies like AWS, Azure, GCP"
]

# === Helper: Extract keywords from previous answer ===
def extract_keywords(text: str) -> List[str]:
    words = text.lower().split()
    keywords = []
    for skill in resume_context["skills"]:
        if skill.lower() in text.lower():
            keywords.append(skill)
    for cert in resume_context["certifications"]:
        if cert.lower() in text.lower():
            keywords.append(cert)
    for proj in resume_context["projects"]:
        if proj.lower() in text.lower():
            keywords.append(proj)
    return keywords


# === Tool: Ask next interview question ===
@mcp.tool()
def get_next_interview_question(previous_answer: str = "") -> str:
    global question_count

    # Stop asking questions after the limit
    if question_count >= MAX_QUESTIONS:
        return "Thank you for answering all the questions. Let me summarize your performance..."

    # Save the previous answer
    if previous_answer.strip():
        interview_history.append(previous_answer)

    question_count += 1

    # First question
    if question_count == 1:
        return "Let's begin. Can you tell me a bit about yourself and your interest in this role?"

    # Extract follow-up keywords
    keywords = extract_keywords(previous_answer)

    if keywords:
        keyword = random.choice(keywords)
        return f"Interesting! Can you go deeper into how you applied {keyword} in a real-world scenario?"

    # Ask JD-aligned topic if not already covered
    for topic in jd_topics:
        if topic not in asked_topics:
            asked_topics.add(topic)
            return f"Can you share your understanding or experience with {topic}?"

    # Resume-based fallback
    categories = ["skills", "certifications", "experience", "projects"]
    for category in categories:
        if category not in asked_topics:
            asked_topics.add(category)
            item = random.choice(resume_context[category])
            return f"Can you explain more about \"{item}\" from your {category}?"

    return "Thanks for sharing! Let me now provide an overview of your performance."


# === Tool: Reset session ===
@mcp.tool()
def reset_interview_state() -> str:
    """Reset the interview state for a new session"""
    asked_topics.clear()
    interview_history.clear()
    global question_count
    question_count = 0
    return "Interview session has been reset. Ready to start fresh."


# === Tool: Generate final feedback ===
@mcp.tool()
def generate_final_feedback() -> str:
    """
    Summarize the candidate's strengths, weaknesses, and alignment with the job role.
    """

    text = " ".join(interview_history).lower()
    strengths = []
    weaknesses = []
    score = 0

    # Check for core concepts
    if "oops" in text or "object oriented" in text:
        strengths.append("Good understanding of OOPs concepts")
        score += 1
    else:
        weaknesses.append("Didn't mention Object Oriented Programming concepts")

    if "data structure" in text or "algorithm" in text:
        strengths.append("Comfortable with DSA")
        score += 1
    else:
        weaknesses.append("Didn't highlight Data Structures and Algorithms")

    if any(proj in text for proj in ["project", "internship"]):
        strengths.append("Project/internship experience mentioned")
        score += 1
    else:
        weaknesses.append("No academic project/internship details")

    if "git" in text:
        strengths.append("Familiar with Git/version control")
        score += 1

    if "html" in text or "css" in text or "javascript" in text:
        strengths.append("Basic web technologies are understood")
        score += 1

    if "database" in text or "mongodb" in text:
        strengths.append("Worked with databases")
        score += 1

    if "team" in text or "collaborat" in text:
        strengths.append("Strong communication and teamwork")
        score += 1

    if any(fw in text for fw in ["react", "node", "django", "spring"]):
        strengths.append("Exposure to modern frameworks")
        score += 1

    if any(cloud in text for cloud in ["azure", "aws", "gcp"]):
        strengths.append("Basic knowledge of cloud platforms")
        score += 1

    rating = min(10, score)

    feedback = f"""
Candidate Feedback:

**Strengths:**
- {', '.join(strengths) if strengths else 'None noted'}

**Areas of Improvement:**
- {', '.join(weaknesses) if weaknesses else 'No major gaps identified'}

**Rating:** {rating}/10  
**Conclusion:** Based on your responses, you demonstrate a{' solid' if rating >= 7 else ' decent'} alignment with the role of a Software Engineer (Fresher). Keep honing your fundamentals and practical exposure.
"""

    return feedback.strip()


# === Resource: Greeting ===
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Personalized greeting"""
    return f"Hi {name}, I'm your interview assistant. Let's begin reviewing your resume together."


# === Run MCP server ===
if __name__ == "__main__":
    mcp.run()
