import os
import subprocess
import json
import requests

# Folder where resumes are synced locally
RESUME_FOLDER = "C:/Users/PoojaDharshiniBoopat/JMAN Group Ltd/All Hands - JHire"
API_URL = "http://localhost:3000/api/extractResumeDetails"  

def process_resume(file_path):
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        # Call your extractResume.py script
        process = subprocess.Popen(
            ["C:/Users/PoojaDharshiniBoopat/AppData/Local/Programs/Python/Python310/python.exe", "C:/Users/PoojaDharshiniBoopat/Downloads/JHire-dev/JHire-dev/scripts/extract_Resume.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=pdf_bytes)

        if process.returncode != 0:
            raise Exception(stderr.decode())

        resume_data = json.loads(stdout.decode())
        print("Extracted:", resume_data)

        return resume_data
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def upload_to_api(resume_data, file_name):
    try:
        with open(os.path.join(RESUME_FOLDER, file_name), "rb") as f:
            files = {'files': (file_name, f, 'application/pdf')}
            data = {
                'college': 'AUTO',  # Or parse from folder if needed
                'exam_date': '2025-08-01T10:00',  # Default
                'expiry_date': '2025-08-10T10:00'  # Default
            }
            response = requests.post(API_URL, files=files, data=data)

        if response.status_code == 200:
            print(f" Uploaded: {file_name}")
        else:
            print(f" Upload failed for {file_name}: {response.text}")
    except Exception as e:
        print(f" Error uploading {file_name}: {e}")

def run():
    for file_name in os.listdir(RESUME_FOLDER):
        if file_name.endswith(".pdf"):
            file_path = os.path.join(RESUME_FOLDER, file_name)
            print(f" Processing {file_name}")
            resume_data = process_resume(file_path)
            if resume_data:
                upload_to_api(resume_data, file_name)

if __name__ == "__main__":
    run()
