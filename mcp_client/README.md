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
├── main.py     # Main MCP server with interview logic
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

# Setup steps
1. Install Claude Desktop
2. Install uv by running `pip install uv`
3. Run `uv init my-first-mcp-server` to create a project directory
4. Run `uv add "mcp[cli]"` to add mcp cli in your project
5. Few folks may get type errors for which you can run `pip install --upgrade typer` to upgrade typer library to its latest version
6. Write code in main.py for leave management server
7. Install this server inside Claude desktop by running `uv run mcp install main.py` in the project directory
8. Kill any running instance of Claude from Task Manager. Restart Claude Desktop
9. In Claude desktop, now you will see tools from this server

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

