# orchestrator.py
import pandas as pd
from extractor_agent import extract_resumes
from categorizer_agent import categorize_resume
from datetime import datetime
import os

def main():
    print("Extracting resumes from SharePoint...")
    extracted_data = extract_resumes()

    if not extracted_data:
        print("No new resumes extracted.")
        return

    print(f" Processing {len(extracted_data)} new resumes for categorization...")
    for resume in extracted_data:
        text_data = (
            f"Skills: {resume.get('Technical Skills', '')}, "
            f"Education: {resume.get('Degrees', '')}, "
            f"Certification: {resume.get('Certifications (if any)', '')}, "
            f"Experience: {resume.get('Work Experience', '')}"
        )
        resume['Category'] = categorize_resume(text_data)

    # Load existing file if present
    output_path = "resumes.xlsx"
    if os.path.exists(output_path):
        try:
            existing_df = pd.read_excel(output_path)
        except Exception as e:
            print(f"Warning: Couldn't read existing Excel file: {e}")
            existing_df = pd.DataFrame()
    else:
        existing_df = pd.DataFrame()

    # Merge old + new data
    new_df = pd.DataFrame(extracted_data)
    new_df['LoadTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)

    # Remove duplicates based on 'File Name'
    combined_df.drop_duplicates(subset=['File Name'], keep='last', inplace=True)

    # Put 'File Name' as the first column if it exists
    if 'File Name' in combined_df.columns:
        cols = ['File Name'] + [col for col in combined_df.columns if col != 'File Name']
        combined_df = combined_df[cols]


    # Save final combined data
    combined_df.to_excel(output_path, index=False)
    print(f" Final results saved to {output_path}")

if __name__ == "__main__":
    main()
