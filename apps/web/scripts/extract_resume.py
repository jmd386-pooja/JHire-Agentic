import sys
import json
import PyPDF2
import io
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini API
genai.configure(api_key=API_KEY)

# Extract text from PDF
def extract_text_from_pdf(pdf_bytes):
    text = ""
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        reader = PyPDF2.PdfReader(pdf_stream)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"Error extracting PDF text: {e}", file=sys.stderr)
    return text.strip()

# Use Gemini API to extract candidate details
def extract_with_gemini(resume_text):
    system_prompt = """You are an AI assistant that extracts structured candidate details from a resume.
Return the following fields in valid JSON format:

- name (string)
- email (string)
- phone (string)
- skills (array of strings)
- UG_college (string, optional)
- UG_cgpa (string, optional)
- UG_year_of_passing (string, optional)
- PG_college (string, optional)
- PG_cgpa (string, optional)
- PG_year_of_passing (string, optional)
- projects (array of strings)
- certifications (array of strings, optional)
- experience (string or array of strings, optional)
- fileName (string)

Only return a valid JSON response without any explanations.
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        response = model.generate_content([system_prompt, resume_text])

        # Pick the text from response
        if hasattr(response, "text") and response.text:
            content = response.text
        elif response.candidates:
            parts = response.candidates[0].content.parts
            content = "".join(p.text for p in parts if hasattr(p, "text"))
        else:
            raise ValueError("Empty response from Gemini API")

        # --- 🛠 FIX: clean code block wrappers ---
        content = (
            content.replace("```json", "")
                   .replace("```", "")
                   .strip()
        )
        if content.lower().startswith("json"):
            content = content[4:].strip()


        return json.loads(content)

    except Exception as e:
        import traceback
        print("Gemini API failed:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {}

# Main entry
if __name__ == "__main__":
    try:
        pdf_bytes = sys.stdin.buffer.read()
        if not pdf_bytes:
            print(json.dumps({"error": "No PDF data received."}))
            sys.exit(1)

        resume_text = extract_text_from_pdf(pdf_bytes)
        if not resume_text:
            print(json.dumps({"error": "Failed to extract text from PDF."}))
            sys.exit(1)

        result = extract_with_gemini(resume_text)
        print(json.dumps(result, indent=4))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
