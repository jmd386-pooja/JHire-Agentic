import google.generativeai as genai
import sys
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY=os.getenv("GEMINI_API_KEY")

class CodeEvaluate:
    def __init__(self, api_key1):
        self.api_key = api_key1

        """Initialisng the model of gemini :: Currently using 1.5-flash"""
        genai.configure(api_key = api_key1)        
        self.model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        
    def start_evaluating(self,context):
        """Using prompt to Evaluate code"""
        try:
            response = self.model.generate_content(context)
            response_content = response.candidates[0].content.parts[0].text
            print(response_content)
        except Exception as e:
            return "I'm having trouble processing your response. Please contact our support team."

if __name__ == "__main__":

    """Extracting the context from system argument list"""
    context = sys.argv
       
    """Creating an instance of Interview Agent Class"""  
    evaluater = CodeEvaluate(API_KEY)

    """Starting the interview"""   
    evaluater.start_evaluating(context)
