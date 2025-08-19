import google.generativeai as genai
import sys
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY=os.getenv("GEMINI_API_KEY")

class DynamicInterviewAgent:
    def __init__(self, api_key1):
        self.api_key = api_key1

        """Initialisng the model of gemini :: Currently using 1.5-flash"""
        genai.configure(api_key = api_key1)        
        self.model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    def chat_with_agent(self, context):
        """Function to send a message to the Gemini API and get a dynamic follow-up question."""
        try:
            prompt = (
                f"Taking into account the conversation history provided in the {context}, analyze the conversation history for the questions asked and the responses given.\n\n"
                f"- Return only the next follow-up question with no additional text, explanation, or data.\n"
                f"- If the user's response does not align with the question, return '0'.\n"
                f"- If the context is empty or there is no valid question-answer pair, return 'Tell me about yourself.'"
            )

            response = self.model.generate_content(prompt)
            response_content = response.candidates[0].content.parts[0].text
            return response_content
        except Exception as e:
            return "I'm having trouble processing your response. Please contact our support team."
        
    def start_interview(self,context):

        """Function to conduct the interview."""

        current_question = self.chat_with_agent(context)
        if current_question == "0\n":
            print("The interview is terminated due to vague answers")
        else:   
            print(f"{current_question}")

if __name__ == "__main__":

    """Extracting the context from system argument list"""
    context = sys.argv[1]
       
    """Creating an instance of Interview Agent Class"""  
    interviewer = DynamicInterviewAgent(API_KEY)

    """Starting the interview"""   
    interviewer.start_interview(context)





