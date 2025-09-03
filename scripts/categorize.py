import os
import requests
from dotenv import load_dotenv
 
 
load_dotenv()
mistral_api_key = os.getenv('MISTRAL_API_KEY')
mistral_api_endpoint = 'https://api.mistral.ai/v1/chat/completions'
 
categories = {
    'Data Science': 'machine learning, data analysis, statistics, Python, R',
    'Data Engineering': 'ETL, SQL, Hadoop, Spark, data pipeline',
    'Full Stack': 'JavaScript, React, Node.js, HTML, CSS, MongoDB'
}
 
def categorize_resume(text_data: str) -> str:
    prompt = f"""
Categorize the following resume into one or more of the following categories (you can choose multiple by separating them with "|"):{categories}
 
- Data Science
- Data Engineering
- Full Stack
 
If the resume clearly does not fit into any of these, return "Other".
Return only the category name(s) exactly as listed above.
Don't add any explanation, quotes, markdown, or additional text. No sentences. Just the category name(s).
You can also give the combination of categories like "Data Science|Data Engineering" if it fits both.
Resume Text:
{text_data}
"""
 
    headers = {
        'Authorization': f'Bearer {mistral_api_key}',
        'Content-Type': 'application/json'
    }
 
    data = {
        "model": "mistral-small",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10,
        "temperature": 0
    }
 
    try:
        response = requests.post(mistral_api_endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"Categorization error: {e}")
        return "Other"
 
 
 
 
 