import { NextResponse } from 'next/server';
import { spawn } from 'child_process';

export async function POST(req: Request) : Promise<Response>{
  try {
  const data = await req.json();
  const dataString = data.value;
  
  // Prepare the context for the question generation
  const nextQuestionContext = JSON.stringify(dataString);
  const job_description = `
    Job Title: Software Engineer  
    Department: Delivery  
    Band/Grade: B1  
    Reports To: Delivery Team  
    Reports From: Project Lead / Sr. Software Engineer  

    Role Overview:  
    - Responsible for software development.  

    Essential Duties and Responsibilities: 
    - Routine Tasks:  
      - Software programming in any language with a well-designed and efficient code structure.  
      - Troubleshooting, debugging, and maintaining code; updating as required.  
      - Compliance with project plans and company standards.  
      - Clear understanding of project requirements and task execution.  
    - Occasional/Other Tasks:  
      - Documenting system/application details and findings in detail.  
      - Collaborating with other developers and departments. 

    Position Requirements:
    - Education: B.E./B.Tech in Computer Science/IT, MCA, MSc IT.  
    - Experience: 0-1 year in software development.  

    Skills:  
    - Proficiency in software programming.  
    - Ability to document requirements and specifications.  
    - Excellent knowledge of the latest technologies.  
    - Strong written and spoken communication skills in English.  

    Good to Have: 
    - Hands-on experience in full-stack programming.  
    - Relevant certifications.  

    Preferential Skills:  
    - Hands-on experience in live projects.  
    - Client handling skills.  
    - Ability to learn, adapt, and grow.  

    Job Location: Chennai  
  `
  const context = `
    You are a Technical Interviewer assigned to conduct an adaptive technical interview for JMAN Group for a job titled Software Engineer. 
    Your primary responsibility is to assess the candidate's technical knowledge, problem-solving skills, and overall suitability for the role as outlined in the provided job description. 

    Guidelines for the Interview:
    1. Professionalism and Tone: 
      - Be polite, soft-spoken, and considerate throughout the interview.
      - Maintain a professional yet approachable demeanor to ensure the candidate feels comfortable expressing their thoughts.
3010
    2. Role-Specific Focus:
      - Base your questions on the specific requirements of the job description: ${job_description}.
      - Ensure the questions assess the candidate's technical skills, adaptability, and problem-solving abilities relevant to the role.

    3. Dynamic and Context-Aware Questions:
      - Use this object array of conversation history /n/n (${nextQuestionContext}) /n/n to craft context-aware follow-up questions.  
        - When "isuser" is "true", the text field in that object represents a response from the candidate.  
        - When "isuser" is "false",the text field in that object represents a question previously asked by you.
      - Build on the candidate's responses. For example:
        - If the candidate mentions proficiency in Java, inquire about their strongest areas in Java or ask for examples of past projects involving Java.
        - If they highlight teamwork experience, ask about their role in collaborative projects or challenges they faced.

    4. Resilience to Vague Answers:
      - If the candidate provides vague or unclear answers, gently guide them to elaborate by asking clarifying questions or providing specific examples to prompt detailed responses.
      - Avoid pressuring the candidate, but ensure the questions encourage them to provide relevant insights.

    5. Flow of the Interview:
      - Begin with introductory questions to set a comfortable tone.
      - Gradually dive deeper into technical topics, aligning with the skills and experiences mentioned in the job description and their responses.
      - End the interview by summarizing their strengths and addressing any final thoughts or questions they might have.

    6. Soft Skills Assessment:
      - Where appropriate, include questions to evaluate the candidate's communication, teamwork, and ability to adapt to new challenges.

    Purpose:
    Your goal is to conduct a structured, engaging, and professional interview evaluating technical skills, making candidate feel valued and understood throughout the interview.
  `
    return new Promise((resolve, reject) => {
    const pythonProcess = spawn('python', ['QuestionGeneration.py', context]);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });
      

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          resolve(NextResponse.json({ nextQuestion: output }));
        } else {
          console.error('Python script error:', errorOutput);
          reject(NextResponse.json({ error: 'Failed to generate question' }, { status: 500 }));
        }
      });
    });
  } catch (error) {
    console.error('Error in POST handler:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
