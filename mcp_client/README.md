# MCP Resume Interviewer – Fresher Software Engineer Edition

This project implements a **dynamic interview assistant** using the [FastMCP](https://pypi.org/project/mcp/) framework.  
It simulates an **AI-driven interviewer** for the role of a **Software Engineer – Fresher**.  
The interviewer:
- Asks **10–15 targeted questions**.
- Covers **most relevant topics** from the candidate’s resume & job description.
- Adapts follow-up questions based on answers.
- Generates **final feedback** with **strengths**, **weaknesses**, and a **rating** out of 10.

---

## Features
- **Job description aligned** – OOPs, DSA, Git, Web Tech, Databases, Cloud, Projects, Teamwork.
- **Dynamic questioning** – Follows up based on detected keywords in answers.
- **Limited questions** – Stops after 10–15 questions to simulate a real interview.
- **Performance summary** – Final feedback with candidate rating based on responses.
- **State management** – Reset interview session anytime.

---

## 🛠 Tech Stack
- **Python 3.9+**
- [FastMCP](https://pypi.org/project/mcp/) – Minimal MCP server framework
- Standard Python libraries: `random`, `typing`

---

## Project Structure
```
resume_interviewer/
│
├── interviewer.py     # Main MCP server with interview logic
├── README.md          # Project documentation
└── requirements.txt   # Python dependencies
```

---

## Installation

1. **Clone this repository**  
```bash
git clone https://github.com/yourusername/mcp-resume-interviewer.git
cd mcp-resume-interviewer
```

2. **Create and activate virtual environment** (optional but recommended)  
```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

3. **Install dependencies**  
```bash
pip install -r requirements.txt
```

---

## Usage

### **Run the MCP server**
```bash
python interviewer.py
```

This starts the MCP server named **"ResumeInterviewer"**.

---

## API Tools

### `get_next_interview_question(previous_answer: str)`
- **Purpose:** Get the next interview question based on the candidate’s last answer.
- **Logic:**
  - First question → self-introduction.
  - Covers JD-specific topics and resume details.
  - Uses keyword extraction for follow-up questions.
  - Stops after the question limit is reached.

### `reset_interview_state()`
- **Purpose:** Clears interview progress for a new session.

### `generate_final_feedback()`
- **Purpose:** Summarizes:
  - Candidate’s **strengths**
  - **Weaknesses**
  - **Rating out of 10**
  - Conclusion on suitability for the job.

### `greeting://{name}`
- **Purpose:** Returns a personalized greeting message.

---

##  How the Interview Works
1. Starts with **"Tell me about yourself"**.
2. Rotates through JD-aligned topics like:
   - OOPs, DSA
   - Git, Web tech
   - Databases
   - Frameworks
   - Cloud basics
   - Teamwork
   - Projects
3. Tracks **asked topics** to avoid repetition.
4. After the limit (e.g., 12 questions) → **Final feedback**.

