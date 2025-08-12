# import fitz  # PyMuPDF
# import os
# import requests
# import pandas as pd
# import json
# import re
# from typing import List
# from dotenv import load_dotenv
# from sharepoint_integration import get_pdf_files_from_sharepoint
# import io
# from datetime import datetime
# import time
# import re



# # Load environment variables
# load_dotenv()
# api_key = os.getenv("GROQ_API_KEY")


# # ---- 1. Load PDF files and extract text ----
# def extract_text_from_pdfs(pdf_paths: List[str]) -> str:
#     all_text = ""
#     for path in pdf_paths:
#         with fitz.open(path) as doc:
#             for page in doc:
#                 all_text += page.get_text()
#     return all_text.strip()


# # ---- 2. Split text into chunks ----
# def split_text(text: str, chunk_size=1000, chunk_overlap=200) -> List[str]:
#     chunks = []
#     start = 0
#     while start < len(text):
#         end = min(start + chunk_size, len(text))
#         chunks.append(text[start:end])
#         start += chunk_size - chunk_overlap
#     return chunks


# # ---- 3. Generate prompt ----
# def generate_prompt(chunk: str) -> str:
#     return f"""You are an AI assistant helping extract structured information from resumes.

#     extract the proper fields from the resume text provided below and place them in the appropriate fields.
#     make sure that you extract the following fields and return them in **valid JSON** format
#     chemical engineering is a part of engineering, so if the resume has chemical engineering degree, then it should be in educational background and in colleges
    
# Extract the following fields and return them in **valid JSON** format:

# {{
#   "Full Name": "...",
#   "Email": "...",
#   "Phone Number": "...",
#   "Colleges": "...",
#   "Degrees": "...",
#   "Year": "...",
#   "CGPA": "...",
#   "Technical Skills": "...",
#   "Certifications (if any)": "...",
#   "Work Experience": "..."
# }}

# Resume Text:
# \"\"\"{chunk}\"\"\"



#  """


# # ---- 4. Query Groq LLaMA model ----
# def query_groq_llama(prompt: str, api_key: str, max_retries: int = 5) -> str:
#     import time

#     url = "https://api.groq.com/openai/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
#         "messages": [{"role": "user", "content": prompt}],
#         "temperature": 0.3
#     }

#     for attempt in range(max_retries):
#         response = requests.post(url, headers=headers, json=payload)

#         if response.status_code == 200:
#             data = response.json()
#             return data['choices'][0]['message']['content']

#         elif response.status_code == 429:
#             try:
#                 error_info = response.json()
#                 wait_time = float(re.search(r"try again in ([\d.]+)s", error_info.get("error", {}).get("message", "")).group(1))
#             except Exception:
#                 wait_time = 10  # Fallback wait time

#             print(f"Rate limit hit. Sleeping for {wait_time} seconds...")
#             time.sleep(wait_time)
#         else:
#             raise Exception(f"Groq API Error {response.status_code}: {response.text}")

#     raise Exception("Exceeded maximum retries for Groq API.")



# # ---- 5. Parse LLM response ----
# def parse_llm_response(response: str) -> dict:
#     # Try extracting JSON from markdown blocks
#     try:
#         match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
#         clean_json = match.group(1) if match else response.strip()
#         return json.loads(clean_json)
#     except Exception:
#         print("LLM response is not valid JSON. Falling back to regex.")
#         return fallback_regex_parser(response)


# # ---- 6. Fallback regex parser ----
# def fallback_regex_parser(response: str) -> dict:
#     fields = {
#         "full name": "Full Name",
#         "email": "Email",
#         "phone number": "Phone Number",
#         "college" : "Colleges",
#         "degrees": "Degrees",
#         "year" : "Years",
#         "cgpa" : "CGPA",
#         "technical skills": "Technical Skills",
#         "certifications": "Certifications (if any)",
#         "work experience": "Work Experience"
#     }
#     result = {v: "" for v in fields.values()}
#     for line in response.splitlines():
#         if ":" in line:
#             key_part, value_part = line.split(":", 1)
#             key = key_part.lower().replace("*", "").strip()
#             value = value_part.strip()
#             for match_key, actual_name in fields.items():
#                 if match_key in key:
#                     result[actual_name] = value
#                     break
#     return result


# def merge_chunk_results(results: List[dict]) -> dict:
#     merged = {}
#     for field in [
#         "Full Name", "Email", "Phone Number",
#         "Colleges","Degrees", "Year", "CGPA", "Technical Skills",
#         "Certifications (if any)", "Work Experience"
#     ]:
#         values = [str(res[field]) for res in results if field in res and str(res[field]).strip()]
#         merged[field] = "; ".join(dict.fromkeys(values)) if values else ""
#     return merged



# def save_to_excel(data: List[dict], output_path):
#     new_df = pd.DataFrame(data)
#     new_df['LoadTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     if os.path.exists(output_path):
#         existing_df = pd.read_excel(output_path)
#         # Only add new entries that don't already exist based on File Name
#         new_df = new_df[~new_df["File Name"].isin(existing_df["File Name"])]
#         combined_df = pd.concat([existing_df, new_df], ignore_index=True)
#     else:
#         combined_df = new_df

#     ordered_columns = ["File Name", "Full Name", "Email", "Phone Number",
#                        "Colleges","Degrees", "Year", "CGPA",
#                        "Technical Skills", "Certifications (if any)",
#                        "Work Experience", "LoadTime"]

#     ordered_columns = [col for col in ordered_columns if col in combined_df.columns]
#     combined_df = combined_df[ordered_columns]

#     combined_df.to_excel(output_path, index=False)
#     print(f" Resume data saved to {output_path}")



# if __name__ == "__main__":
#     # Load existing file names from Excel if it exists
#     existing_file_names = set()
#     output_path = "new.xlsx"

#     if os.path.exists(output_path):
#         try:
#             existing_df = pd.read_excel(output_path)
#             existing_file_names = set(existing_df["File Name"].dropna().unique())
#         except Exception as e:
#             print(f"Warning: Couldn't read existing Excel file: {e}")






#     # Fetch PDF files from SharePoint
#     pdf_files = get_pdf_files_from_sharepoint()

#     final_results = []

#     for index, file in enumerate(pdf_files):
#         file_name = file['name']

#         # Skip already processed resumes
#         if file_name in existing_file_names:
#             print(f"Skipping already processed: {file_name}")
#             continue

#         download_url = file.get('@microsoft.graph.downloadUrl')

#         if not download_url:
#             print(f"Skipping {file_name} (no download URL found)")
#             continue

#         print(f"\nProcessing: {file_name}")

#         try:
#             response = requests.get(download_url)
#             response.raise_for_status()
#             pdf_data = response.content

#             # Extract text directly from in-memory PDF bytes
#             with fitz.open(stream=io.BytesIO(pdf_data), filetype="pdf") as doc:
#                 text = "".join(page.get_text() for page in doc)

#             chunks = split_text(text) if len(text) > 1500 else [text]

#             all_chunks_result = []
#             chunk_counter = 0
#             for i, chunk in enumerate(chunks):
#                 print(f"   Chunk {i + 1}/{len(chunks)}")
#                 try:
#                     prompt = generate_prompt(chunk)
#                     result = query_groq_llama(prompt, api_key)
#                     parsed = parse_llm_response(result)
#                     all_chunks_result.append(parsed)
#                 except Exception as e:
#                     print(f"  Error in chunk {i + 1}: {e}")

#             if all_chunks_result:
#                 merged_result = merge_chunk_results(all_chunks_result)
#                 # merged_result = split_education_and_cgpa(merged_result)
#                 merged_result["File Name"] = file_name
#                 final_results.append(merged_result)

#         except Exception as e:
#             print(f" Failed to process {file_name}: {e}")

#         # chunk_counter += 1
#         # if chunk_counter % 5 == 0:
#         #     print(f"Processed {chunk_counter} chunks. Sleeping for 10 seconds...\n")
#         #     time.sleep(10)

#     if final_results:
#         save_to_excel(final_results, output_path)
#     else:
#         print(" No valid resumes processed.")
    



from typing import List, Dict
import fitz
import os
import requests
import pandas as pd
import json
import re
import io
from dotenv import load_dotenv
from datetime import datetime
from sharepoint_integration import get_pdf_files_from_sharepoint
import time

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")


def extract_resumes() -> List[Dict]:
    """
    Extracts structured resume data from SharePoint PDFs using Groq API.
    Returns: List of dicts containing extracted resume fields.
    """
    output_path = "resumes.xlsx"
    existing_file_names = set()

    # Load existing data if available
    if os.path.exists(output_path):
        try:
            existing_df = pd.read_excel(output_path)
            existing_file_names = set(existing_df["File Name"].dropna().unique())
        except Exception as e:
            print(f"Warning: Couldn't read existing Excel file: {e}")

    # ---- Helper: Split text into chunks ----
    def split_text(text: str, chunk_size=1000, chunk_overlap=200) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap
        return chunks

    # ---- Helper: Generate prompt for LLM ----
    def generate_prompt(chunk: str) -> str:
        return f"""You are an AI assistant helping extract structured information from resumes.

    Extract the following fields and return them in **valid JSON** format:

    {{
      "Full Name": "...",
      "Email": "...",
      "Phone Number": "...",
      "Colleges": "...",
      "Degrees": "...",
      "Year": "...",
      "CGPA": "...",
      "Technical Skills": "...",
      "Certifications (if any)": "...",
      "Work Experience": "..."
    }}

    Resume Text:
    \"\"\"{chunk}\"\"\""""

    # ---- Helper: Query Groq LLaMA API ----
    def query_groq_llama(prompt: str, api_key: str, max_retries: int = 5) -> str:
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

        retries = 0
        while retries < max_retries:
            response = requests.post(url, headers=headers, json=payload)

            # Success
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']

            # Rate limit
            if response.status_code == 429:
                wait_time = int(response.headers.get("Retry-After", 2 ** retries))
                print(f"Rate limited. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                retries += 1
                continue

            # Other error
            raise Exception(f"Groq API Error {response.status_code}: {response.text}")

        raise Exception(f"Failed after {max_retries} retries due to rate limiting.")



    # ---- Helper: Parse LLM response ----
    def parse_llm_response(response: str) -> dict:
        try:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
            clean_json = match.group(1) if match else response.strip()
            return json.loads(clean_json)
        except Exception:
            print("LLM response is not valid JSON. Falling back to regex.")
            return fallback_regex_parser(response)

    # ---- Helper: Fallback regex parser ----
    def fallback_regex_parser(response: str) -> dict:
        fields = {
            "full name": "Full Name",
            "email": "Email",
            "phone number": "Phone Number",
            "college": "Colleges",
            "degrees": "Degrees",
            "year": "Year",
            "cgpa": "CGPA",
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

    # ---- Helper: Merge chunk results ----
    def merge_chunk_results(results: List[dict]) -> dict:
        merged = {}
        for field in [
            "Full Name", "Email", "Phone Number",
            "Colleges", "Degrees", "Year", "CGPA",
            "Technical Skills", "Certifications (if any)", "Work Experience"
        ]:
            values = [str(res[field]) for res in results if field in res and str(res[field]).strip()]
            merged[field] = "; ".join(dict.fromkeys(values)) if values else ""
        return merged

    # ---- Helper: Save results to Excel ----
    def save_to_excel(data: List[dict], output_path="final_resu.xlsx"):
        df = pd.DataFrame(data)

        # Reorder columns: File Name first
        ordered_columns = ["File Name", "Full Name", "Email", "Phone Number", 
                           "Educational Background", "CGPA", "Technical Skills", 
                           "Certifications (if any)", "Work Experience"]

        # Only keep columns that exist (in case of any missing fields)
        ordered_columns = [col for col in ordered_columns if col in df.columns]
        df = df[ordered_columns]

        # Drop rows where all fields (except File Name) are empty
        # df.dropna(subset=[col for col in df.columns if col != "File Name"], how='all', inplace=True)

        df.to_excel(output_path, index=False)
        print(f" Resume data saved to {output_path}")




    # ---- Process resumes from SharePoint ----
    pdf_files = get_pdf_files_from_sharepoint()

    final_results = []

    for file in pdf_files:
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
                # merged_result = split_education_and_cgpa(merged_result)
                merged_result["File Name"] = file_name
                final_results.append(merged_result)

        except Exception as e:
            print(f" Failed to process {file_name}: {e}")
    return final_results
