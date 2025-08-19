# import sys
# import os
# import json
# import PyPDF2

# try:
#     import google.generativeai as genai
#     genai.configure(api_key="AIzaSyALsWBF5unjSOq_1aLdFxizUs7QHcvpgqE")  # Replace with your API key
#     AI_ENABLED = True
# except ImportError:
#     AI_ENABLED = True


# # Function to extract text from a PDF
# def extract_text_from_pdf(pdf_path):
#     text = ""
#     try:
#         with open(pdf_path, "rb") as file:
#             reader = PyPDF2.PdfReader(file)
#             for page in reader.pages:
#                 text += page.extract_text() or ""
#     except Exception as e:
#         print(f"Error reading PDF: {e}")
#     return text


# # Function to extract details using regex
# def extract_details_with_regex(text):
#     import re
#     try:
#         name_regex = r"'name':\s*'([^']*)'"
#         email_regex = r"'email':\s*'([^']*)'"
#         phone_regex = r"'phone':\s*'([^']*)'"
#         skills_regex = r"'skills':\s*\[([^\]]*)\]"

#         name = re.search(name_regex, text)
#         email = re.search(email_regex, text)
#         phone = re.search(phone_regex, text)
#         skills = re.search(skills_regex, text)

#         return {
#             "name": name.group(1).strip() if name else "Not Found",
#             "email": email.group(1).replace(" ", "") if email else "Not Found",
#             "phone": phone.group(1).strip() if phone else "Not Found",
#             "skills": [skill.strip() for skill in (skills.group(1).split(",") if skills else [])],
#         }
#     except Exception as e:
#         print(f"Error extracting details with regex: {e}")
#         return {}


# # Optional: Function to get candidate details using AI
# def get_candidate_details_with_ai(text):
#     if not AI_ENABLED:
#         return extract_details_with_regex(text)

#     try:
#         prompt = (
#             f"""Extract the candidate's name, email, phone number, and skills from the following text. 

#             Return the extracted information in JSON format without enclosing it in a code blocks.

#             **Text:** {text}
#             """
#         )
#         response = genai.GenerativeModel(model_name="gemini-1.5-flash").generate_content(prompt)
#         # print(response)
#         if not response or not response.text:
#             return extract_details_with_regex(text)

#         return json.loads(response.text)
#     except Exception as e:
#         print(f"Error processing text with AI: {e}")
#         return extract_details_with_regex(text)


# # Main script
# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print(json.dumps({"error": "PDF file path is required."}))
#         sys.exit(1)

#     pdf_path = sys.argv[1]

#     if not os.path.exists(pdf_path):
#         print(json.dumps({"error": "File not found."}))
#         sys.exit(1)

#     extracted_text = extract_text_from_pdf(pdf_path)

#     if not extracted_text:
#         print(json.dumps({"error": "Failed to extract text from the PDF."}))
#         sys.exit(1)

#     candidate_details = get_candidate_details_with_ai(extracted_text)
#     print(json.dumps(candidate_details, indent=4))




# import sys
# import json
# import PyPDF2
# import io  # Import io for BytesIO
# from dotenv import load_dotenv
# import os

# load_dotenv()
# API_KEY=os.getenv("GEMINI_API_KEY")

# try:
#     import google.generativeai as genai
#     genai.configure(api_key=API_KEY)  # Replace with your API key
#     AI_ENABLED = True
# except ImportError:
#     AI_ENABLED = False

# i=1
# # Function to extract text from a PDF
# def extract_text_from_pdf(pdf_bytes):
#     text = ""
#     try:
#         # Wrap the raw bytes in a BytesIO object to simulate a file-like object
#         pdf_stream = io.BytesIO(pdf_bytes)
#         reader = PyPDF2.PdfReader(pdf_stream)
#         for page in reader.pages:
#             text += page.extract_text() or ""
#     except Exception as e:
#         print(f"Error reading PDF: {e}", file=sys.stderr)
#     return text

# # Function to extract details using regex
# def extract_details_with_regex(text):
#     import re
#     try:
#         name_regex = r"'name':\s*'([^']*)'"
#         email_regex = r"'email':\s*'([^']*)'"
#         phone_regex = r"'phone':\s*'([^']*)'"
#         skills_regex = r"'skills':\s*\[([^\]]*)\]"

#         name = re.search(name_regex, text)
#         email = re.search(email_regex, text)
#         phone = re.search(phone_regex, text)
#         skills = re.search(skills_regex, text)

#         return {
#             "name": name.group(1).strip() if name else f"Not Found {i+3}",
#             "email": email.group(1).replace(" ", "") if email else f"Not Found {i+3}",
#             "phone": phone.group(1).strip() if phone else f"Not Found {i+3}",
#             "skills": [skill.strip() for skill in (skills.group(1).split(",") if skills else [])],
#         }
#     except Exception as e:
#         print(f"Error extracting details with regex: {e}", file=sys.stderr)
#         return {}


# # Optional: Function to get candidate details using AI
# def get_candidate_details_with_ai(text):
#     if not AI_ENABLED:
#         return extract_details_with_regex(text)

#     try:
#         prompt = (
#             f"""Extract the candidate's name, email, phone number, and skills from the following text. 

#             Return the extracted information in JSON format without enclosing it in code blocks.

#             **Text:** {text}
#             """
#         )
#         response = genai.GenerativeModel(model_name="gemini-1.5-flash").generate_content(prompt)
        
#         if not response or not response.text:
#             return extract_details_with_regex(text)

#         return json.loads(response.text)
#     except Exception as e:
#         print(f"Error processing text with AI: {e}", file=sys.stderr)
#         return extract_details_with_regex(text)


# # Main script
# if __name__ == "__main__":
#     try:
#         # Read PDF bytes from stdin
#         pdf_bytes = sys.stdin.buffer.read()

#         if not pdf_bytes:
#             print(json.dumps({"error": "No PDF data received via stdin."}))
#             sys.exit(1)

#         # Extract text from the PDF
#         extracted_text = extract_text_from_pdf(pdf_bytes)

#         if not extracted_text:
#             print(json.dumps({"error": "Failed to extract text from the PDF."}))
#             sys.exit(1)

#         # Process text to extract candidate details
#         candidate_details = get_candidate_details_with_ai(extracted_text)

#         # Return the extracted details as JSON
#         print(json.dumps(candidate_details, indent=4))
#     except Exception as e:
#         print(json.dumps({"error": str(e)}))
#         sys.exit(1)


import sys
import json
import PyPDF2
import io
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

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

# Use Mistral API to extract candidate details
def extract_with_mistral(resume_text):
    system_prompt = """You are an AI assistant that extracts structured candidate details from a resume. 
                        Return the following fields in valid JSON format:

                        - name (string)
                        - email (string)
                        - phone (string)
                        - education (string or array of strings)
                        - skills (array of strings)
                        - projects (array of strings)
                        - certifications (array of strings, optional)
                        - experience (string or array of strings, optional)

                        Only return a valid JSON response without any explanations, like:
                        {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "phone": "+91 9876543210",
                        "education": "B.Tech in Computer Science from XYZ University (2020)",
                        "skills": ["Python", "SQL", "React"],
                        "projects": ["Sentiment Analysis on Twitter", "Inventory Tracker Web App"],
                        "certifications": ["AWS Certified Developer", "Coursera ML Certificate"],
                        "experience": "Software Engineer at ABC Corp for 2 years"
}

"""

    payload = {
        "model": "mistral-medium",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": resume_text}
        ]
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(MISTRAL_URL, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        # Clean up if Mistral returns with ```json blocks
        content = content.strip().strip("`").replace("```json", "").replace("```", "").strip()
        return json.loads(content)

    except Exception as e:
        print(f" Mistral API failed: {e}", file=sys.stderr)
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

        result = extract_with_mistral(resume_text)
        print(json.dumps(result, indent=4))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
