import google.generativeai as genai
import sys
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY=os.getenv("GEMINI_API_KEY")

def evaluate_candidate(context):
    """Rate the candidate based on the responses given by them for the asked questions."""

    genai.configure(api_key = API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    prompt = f"Analyze the user's responses based on the following context: {context}. Rate the user on a scale of 1 to 100. You should not give any explainnation or any other text, just a numerical value representing the score like 20"
    response = model.generate_content(prompt)
    response_content = response.candidates[0].content.parts[0].text
    print(response_content)

if __name__ == "__main__":

    """Extracting the context from system argument list"""
    context = sys.argv[1]

    evaluate_candidate(context)