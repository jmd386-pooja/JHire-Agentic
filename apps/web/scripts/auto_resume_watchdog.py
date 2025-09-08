import time
import os
import subprocess
import json
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Folder to watch (your synced SharePoint folder)
WATCH_FOLDER = "C:/Users/PoojaDharshiniBoopat/JMAN Group Ltd/All Hands - JHire"

# Your extract script and backend API
PYTHON_EXEC = r"C:/Users/PoojaDharshiniBoopat/AppData/Local/Programs/Python/Python310/python.exe"
EXTRACT_SCRIPT = r"C:/Users/PoojaDharshiniBoopat/Downloads/JHire-dev/JHire-dev/scripts/extract_Resume.py"
UPLOAD_URL = "http://localhost:3000/api/extractResumeDetails"

class ResumeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".pdf"):
            print(f" New resume detected: {event.src_path}")
            self.process_resume(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".pdf"):
            print(f" Resume modified: {event.src_path}")
            self.process_resume(event.src_path)


    def process_resume(self, file_path):
        try:
            time.sleep(1)  # wait 1 sec to let SharePoint finish writing
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            # Call your resume extraction script
            process = subprocess.Popen(
                [PYTHON_EXEC, EXTRACT_SCRIPT],  
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=pdf_bytes)

            if process.returncode != 0:
                print(" Error in extraction:", stderr.decode())
                return

            resume_data = json.loads(stdout.decode())
            print(" Extracted:", resume_data)

            # Upload extracted data to backend
            with open(file_path, "rb") as f:
                files = {'files': (os.path.basename(file_path), f, 'application/pdf')}
                data = {
                    "college": "Auto",
                    "exam_date": "2025-08-01T10:00",     # Default or dynamic
                    "expiry_date": "2025-08-10T10:00"     # Default or dynamic
                }
                response = requests.post(UPLOAD_URL, files=files, data=data)

                if response.status_code == 200:
                    print(" Uploaded successfully.")
                else:
                    print(" Upload failed:", response.text)

        except Exception as e:
            print(" Exception during processing:", str(e))

if __name__ == "__main__":
    print(" Watching for new resumes...")
    observer = Observer()
    event_handler = ResumeHandler()

    # Process any existing resumes before watching
    for filename in os.listdir(WATCH_FOLDER):
        file_path = os.path.join(WATCH_FOLDER, filename)
        if os.path.isfile(file_path) and filename.endswith(".pdf"):
            print(f" Found existing resume: {filename}")
            event_handler.process_resume(file_path)

    # Start watching for new files
    observer.schedule(event_handler, WATCH_FOLDER, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
