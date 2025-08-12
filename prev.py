import fitz  # PyMuPDF
import os
import requests
import pandas as pd
import json
import re
from typing import List
from dotenv import load_dotenv
from sharepoint_integration import get_pdf_files_from_sharepoint
import io
from datetime import datetime
import time
import re



# Load environment variables
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")


# ---- 1. Load PDF files and extract text ----
def extract_text_from_pdfs(pdf_paths: List[str]) -> str:
    all_text = ""
    for path in pdf_paths:
        with fitz.open(path) as doc:
            for page in doc:
                all_text += page.get_text()
    return all_text.strip()


# ---- 2. Split text into chunks ----
def split_text(text: str, chunk_size=1000, chunk_overlap=200) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


# ---- 3. Generate prompt ----
def generate_prompt(chunk: str) -> str:
    return f"""You are an AI assistant helping extract structured information from resumes.

    extract the proper fields from the resume text provided below and place them in the appropriate fields.
    make sure that you extract the following fields and return them in **valid JSON** format
    chemical engineering is a part of engineering, so if the resume has chemical engineering degree, then it should be in educational background and in colleges
    
Extract the following fields and return them in **valid JSON** format:

{{
  "Full Name": "...",
  "Email": "...",
  "Phone Number": "...",
  "Educational Background": "...",
  "Technical Skills": "...",
  "Certifications (if any)": "...",
  "Work Experience": "..."
}}

Resume Text:
\"\"\"{chunk}\"\"\"



"""


# ---- 4. Query Groq LLaMA model ----
def query_groq_llama(prompt: str, api_key: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Groq API Error {response.status_code}: {response.text}")
    
    data = response.json()
    return data['choices'][0]['message']['content']


# ---- 5. Parse LLM response ----
def parse_llm_response(response: str) -> dict:
    # Try extracting JSON from markdown blocks
    try:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        clean_json = match.group(1) if match else response.strip()
        return json.loads(clean_json)
    except Exception:
        print("LLM response is not valid JSON. Falling back to regex.")
        return fallback_regex_parser(response)


# ---- 6. Fallback regex parser ----
def fallback_regex_parser(response: str) -> dict:
    fields = {
        "full name": "Full Name",
        "email": "Email",
        "phone number": "Phone Number",
        "educational background": "Educational Background",
        "cgpa" : "CGPA",
        "technical skills": "Technical Skills",
        "certifications": "Certifications (if any)",
        "work experience": "Work Experience"
    }
    result = {v: "" for v in fields.values()}
    for line in response.splitlines():
        if ":" in line:
            key_part, value_part = line.split(":", 1)
            key = key_part.lower().replace("*", "").strip()
            value = value_part.strip()
            for match_key, actual_name in fields.items():
                if match_key in key:
                    result[actual_name] = value
                    break
    return result


import re

def split_education_and_cgpa(entry: dict) -> dict:
    edu_entries = entry.get("Educational Background", "").split("\n")
    split_edu = []
    cgpa_value = ""

    for edu in edu_entries:
        edu = edu.strip()

        # Extract CGPA if present
        cgpa_match = re.search(r"CGPA[:\s]*([0-9.]+/10)", edu, re.IGNORECASE)
        if cgpa_match:
            cgpa_value = cgpa_match.group(1)
            edu = re.sub(r"\|?\s*CGPA[:\s]*[0-9.]+/10", "", edu, flags=re.IGNORECASE).strip()

        # Match patterns like: Degree, College – YYYY or , YYYY or - YYYY
        match = re.match(r"(.*?),\s*(.*?)\s*[–,-]\s*(\d{4})", edu)
        if not match:
            match = re.match(r"(.*?),\s*(.*?)\s*,\s*(\d{4})", edu)

        if match:
            degree = match.group(1).strip()
            college = match.group(2).strip()
            year = match.group(3).strip()
            split_edu.append({
                "Degree": degree,
                "College": college,
                "Year": year
            })

    entry["CGPA"] = cgpa_value
    entry["Education Details"] = split_edu
    return entry





def merge_chunk_results(results: List[dict]) -> dict:
    merged = {}
    for field in [
        "Full Name", "Email", "Phone Number",
        "Educational Background","CGPA", "Technical Skills",
        "Certifications (if any)", "Work Experience"
    ]:
        values = [res[field] for res in results if field in res and res[field].strip()]
        merged[field] = "; ".join(dict.fromkeys(values)) if values else ""
    return merged



def save_to_excel(data: List[dict], output_path="resume_details.xlsx"):
    flattened_data = []

    for entry in data:
        flattened_entry = entry.copy()
        edu_details = flattened_entry.pop("Education Details", [])

        degrees = []
        colleges = []
        years = []

        for edu in edu_details:
            degrees.append(edu.get("Degree", ""))
            colleges.append(edu.get("College", ""))
            years.append(edu.get("Year", ""))

        flattened_entry["Degrees"] = ", ".join(degrees)
        flattened_entry["Colleges"] = ", ".join(colleges)
        flattened_entry["Years"] = ", ".join(years)

        # Add LoadTime column
        flattened_entry["LoadTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        flattened_entry.pop("Educational Background", None)
        flattened_data.append(flattened_entry)

    new_df = pd.DataFrame(flattened_data)

    # Load existing data if file exists
    if os.path.exists(output_path):
        existing_df = pd.read_excel(output_path)
        # Only add new entries that don't already exist based on File Name
        new_df = new_df[~new_df["File Name"].isin(existing_df["File Name"])]
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    ordered_columns = ["File Name", "Full Name", "Email", "Phone Number",
                       "CGPA", "Degrees", "Colleges", "Years",
                       "Technical Skills", "Certifications (if any)",
                       "Work Experience", "LoadTime"]

    ordered_columns = [col for col in ordered_columns if col in combined_df.columns]
    combined_df = combined_df[ordered_columns]

    combined_df.to_excel(output_path, index=False)
    print(f" Resume data saved to {output_path}")




    # Drop rows where all fields (except File Name) are empty
    # df.dropna(subset=[col for col in df.columns if col != "File Name"], how='all', inplace=True)



if __name__ == "__main__":
    # Load existing file names from Excel if it exists
    existing_file_names = set()
    output_path = "resume_details.xlsx"

    if os.path.exists(output_path):
        try:
            existing_df = pd.read_excel(output_path)
            existing_file_names = set(existing_df["File Name"].dropna().unique())
        except Exception as e:
            print(f"Warning: Couldn't read existing Excel file: {e}")






    # Fetch PDF files from SharePoint
    pdf_files = get_pdf_files_from_sharepoint()

    final_results = []

    for index, file in enumerate(pdf_files):
        file_name = file['name']

        # Skip already processed resumes
        if file_name in existing_file_names:
            print(f"Skipping already processed: {file_name}")
            continue

        download_url = file.get('@microsoft.graph.downloadUrl')

        if not download_url:
            print(f"Skipping {file_name} (no download URL found)")
            continue

        print(f"\nProcessing: {file_name}")
        ...




    # for index, file in enumerate(pdf_files):
    #     file_name = file['name']
    #     download_url = file.get('@microsoft.graph.downloadUrl')

    #     if not download_url:
    #         print(f"Skipping {file_name} (no download URL found)")
    #         continue

        # print(f"\nProcessing: {file_name}")

        try:
            response = requests.get(download_url)
            response.raise_for_status()
            pdf_data = response.content

            # Extract text directly from in-memory PDF bytes
            with fitz.open(stream=io.BytesIO(pdf_data), filetype="pdf") as doc:
                text = "".join(page.get_text() for page in doc)

            chunks = split_text(text) if len(text) > 1500 else [text]

            all_chunks_result = []
            for i, chunk in enumerate(chunks):
                print(f"   Chunk {i + 1}/{len(chunks)}")
                try:
                    prompt = generate_prompt(chunk)
                    result = query_groq_llama(prompt, api_key)
                    parsed = parse_llm_response(result)
                    all_chunks_result.append(parsed)
                except Exception as e:
                    print(f"  Error in chunk {i + 1}: {e}")

            if all_chunks_result:
                merged_result = merge_chunk_results(all_chunks_result)
                merged_result = split_education_and_cgpa(merged_result)
                merged_result["File Name"] = file_name
                final_results.append(merged_result)

        except Exception as e:
            print(f" Failed to process {file_name}: {e}")

        if (index + 1) % 5 == 0:
            print("Processed 5 resumes. Sleeping for 10 seconds...\n")
            time.sleep(5)

    if final_results:
        save_to_excel(final_results)
    else:
        print(" No valid resumes processed.")
    