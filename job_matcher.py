import os
from typing import List, Dict, Any, Tuple, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
import json
import re
import chromadb.config

load_dotenv()

# Disable ChromaDB telemetry completely at the system level
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["ALLOW_RESET"] = "TRUE"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "FALSE"
os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "FALSE"

# Disable telemetry at the module level
import chromadb
chromadb.config.Settings.anonymized_telemetry = False

class JobDataExtractor:
    """Extracts and validates required job data for ranking purposes."""
    
    def __init__(self, llm):
        self.llm = llm
        
        # Define all required fields for job ranking
        self.required_fields = {
            "job_title": {
                "description": "Exact job title/position name",
                "required": True,
                "example": "Python Developer"
            },
            "company_name": {
                "description": "Company or organization name",
                "required": True,
                "example": "Jman Group",
                "fixed_value": "Jman Group"
            },
            "industry": {
                "description": "Industry or sector",
                "required": True,
                "example": "Technology",
                "fixed_value": "Software Development"
            },
            "experience_level": {
                "description": "Required experience level",
                "required": True,
                "options": ["entry", "junior", "mid", "senior", "lead", "principal", "executive"],
                "example": "junior"
            },
            "required_skills": {
                "description": "Essential technical skills and competencies",
                "required": True,
                "min_count": 3,
                "example": ["Python", "Programming", "Code Writing"]
            },
            "preferred_skills": {
                "description": "Nice-to-have skills",
                "required": False,
                "example": ["Django", "Flask", "API Development"]
            },
            "key_responsibilities": {
                "description": "Main job duties and responsibilities",
                "required": True,
                "min_count": 3,
                "example": ["Write Python code", "Develop software", "Debug applications"]
            },
            "education_requirements": {
                "description": "Required education level and field",
                "required": True,
                "example": "Degree not required, but Python knowledge essential"
            },
            "location": {
                "description": "Job location (remote/onsite/hybrid)",
                "required": True,
                "example": "Remote"
            },
            "salary_range": {
                "description": "Expected salary range",
                "required": False,
                "example": "Competitive salary based on experience"
            },
            "team_size": {
                "description": "Expected team size or collaboration level",
                "required": False,
                "example": "Individual contributor or small team"
            },
            "project_duration": {
                "description": "Typical project duration or timeline",
                "required": False,
                "example": "Ongoing development projects"
            }
        }
    
    def extract_job_data(self, job_description: str) -> Dict[str, Any]:
        """Extract job data from description using AI with enhanced parsing."""
        prompt = ChatPromptTemplate.from_template("""
        You are an expert HR analyst with 15+ years of experience in job analysis and requirements extraction. 
        Your task is to analyze the following job description and extract comprehensive, accurate information.
        
        Job Description:
        {job_description}
        
        CRITICAL EXTRACTION GUIDELINES:
        1. **Job Title**: Extract the EXACT job title/position name as mentioned, or infer from context
           - Look for: "I want a", "need a", "looking for", "seeking", "position for", "role for"
           - If no explicit title, infer from skills and requirements mentioned
        
        2. **Company Name**: ALWAYS set to "Jman Group" (this is fixed)
        
        3. **Industry**: ALWAYS set to "Software Development" (this is fixed)
        
        4. **Experience Level**: Determine from context - entry/junior/mid/senior/lead/principal/executive
           - Look for keywords: "junior", "entry level", "senior", "experienced", "lead", etc.
           - If "junior" is mentioned, set to "junior"
           - If no level mentioned, infer from context (e.g., "degree not required" suggests entry/junior)
        
        5. **Required Skills**: Extract SPECIFIC technical skills, tools, technologies, and competencies mentioned as REQUIRED
           - Focus on programming languages, frameworks, tools, methodologies
           - Extract both explicit and implicit skill requirements
           - If "need to know python" is mentioned, extract "Python" as required skill
           - If "need to write python code" is mentioned, extract "Python Programming" and "Code Writing" as skills
           - Look for action verbs and technical terms
        
        6. **Preferred Skills**: Extract skills mentioned as "nice to have", "preferred", or "bonus"
           - If no preferred skills mentioned, leave as empty list
        
        7. **Key Responsibilities**: Extract SPECIFIC job duties, tasks, and responsibilities mentioned
           - Look for action verbs and specific tasks
           - Extract both explicit and implicit responsibilities
           - If "need to write python code" is mentioned, extract "Write Python Code" as responsibility
           - If "python developer" is mentioned, extract "Develop Python Applications" as responsibility
        
        8. **Education Requirements**: Extract specific degree requirements and fields of study
           - Note if degree is required or not required
           - Extract field of study if mentioned
           - If "degree is not required" is mentioned, extract this information
        
        9. **Location**: Extract work location details (remote/onsite/hybrid, city, state)
           - Look for keywords: "remote", "onsite", "hybrid", "work from home"
           - If "remote job" is mentioned, extract "Remote" as location
        
        10. **Salary Range**: Extract if explicitly mentioned
        
        11. **Team Size**: Extract team size if mentioned
        
        12. **Project Duration**: Extract project timelines if mentioned
        
        EXTRACTION RULES:
        - Be PRECISE and ACCURATE - don't infer or assume beyond reasonable context
        - For skills: Extract actual mentioned skills, not generic categories
        - For responsibilities: Extract specific tasks, not general descriptions
        - For experience level: Look for years of experience, seniority indicators
        - If information is not explicitly stated, use null
        - Required skills must have at least 3 specific items
        - Key responsibilities must have at least 3 specific items
        - Look for implicit requirements in the description text
        - Pay attention to natural language patterns like "need to", "should know", "must have"
        
        SPECIAL ATTENTION:
        - If the description mentions "degree is not required", extract this information
        - If it mentions "remote job", extract this as location
        - If it mentions specific programming languages or tools, extract them as required skills
        - If it mentions writing code or programming, extract as responsibilities
        - If it mentions "junior developer role", extract "junior" as experience level
        - If it mentions "need to know python", extract "Python" as required skill
        - If it mentions "need to write python code", extract "Python Programming" and "Code Writing" as skills and responsibilities
        
        Respond with ONLY a valid JSON object:
        {{
            "job_title": "exact job title as mentioned or inferred",
            "company_name": "Jman Group",
            "industry": "Software Development",
            "experience_level": "entry/junior/mid/senior/lead/principal/executive",
            "required_skills": ["specific skill 1", "specific skill 2", "specific skill 3", "specific skill 4", "specific skill 5"],
            "preferred_skills": ["specific skill 1", "specific skill 2"],
            "key_responsibilities": ["specific responsibility 1", "specific responsibility 2", "specific responsibility 3", "specific responsibility 4"],
            "education_requirements": "specific education level and field",
            "location": "specific location details",
            "salary_range": "salary range if mentioned",
            "team_size": "team size if mentioned",
            "project_duration": "project timeline if mentioned"
        }}
        
        IMPORTANT: 
        - Return ONLY the JSON object, no additional text, explanations, or markdown
        - Be extremely accurate and specific in extraction
        - Don't make assumptions or add generic content
        - Extract ALL information present in the description
        - Pay special attention to natural language patterns and implicit requirements
        """)
        
        chain = prompt | self.llm
        response = chain.invoke({"job_description": job_description})
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            job_data = json.loads(content)
            
            # Ensure company name is always set to Jman Group
            job_data["company_name"] = "Jman Group"
            job_data["industry"] = "Software Development"  # Always set to Software Development
            
            return job_data
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing job data: {e}")
            return self._get_fallback_data()
    
    def _get_fallback_data(self) -> Dict[str, Any]:
        """Return fallback data structure when parsing fails."""
        return {
            "job_title": None,
            "company_name": "Jman Group",  # Always set to Jman Group
            "industry": "Software Development",  # Always set to Software Development
            "experience_level": None,
            "required_skills": [],
            "preferred_skills": [],
            "key_responsibilities": [],
            "education_requirements": None,
            "location": None,
            "salary_range": None,
            "team_size": None,
            "project_duration": None
        }
    
    def validate_job_data(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted job data and identify missing required fields."""
        validation_result = {
            "is_complete": True,
            "missing_fields": [],
            "validation_errors": [],
            "extracted_data": job_data,
            "completeness_score": 0
        }
        
        total_required = 0
        total_found = 0
        
        for field_name, field_config in self.required_fields.items():
            if field_config["required"]:
                total_required += 1
                field_value = job_data.get(field_name)
                
                # Handle fixed values (like company name)
                if field_config.get("fixed_value"):
                    job_data[field_name] = field_config["fixed_value"]
                    total_found += 1
                    continue
                
                if field_value is None or field_value == "":
                    validation_result["missing_fields"].append({
                        "field": field_name,
                        "description": field_config["description"],
                        "example": field_config.get("example", "N/A")
                    })
                    validation_result["is_complete"] = False
                elif isinstance(field_value, list) and field_config.get("min_count"):
                    if len(field_value) < field_config["min_count"]:
                        validation_result["validation_errors"].append({
                            "field": field_name,
                            "issue": f"Minimum {field_config['min_count']} items required, found {len(field_value)}",
                            "current": field_value
                        })
                        validation_result["is_complete"] = False
                    else:
                        total_found += 1
                else:
                    total_found += 1
        
        # Calculate completeness score
        if total_required > 0:
            validation_result["completeness_score"] = int((total_found / total_required) * 100)
        
        return validation_result
    
    def generate_missing_data_prompt(self, missing_fields: List[Dict]) -> str:
        """Generate a user-friendly prompt for missing data."""
        prompt = "The following required information is missing from the job description:\n\n"
        
        for field_info in missing_fields:
            prompt += f"• **{field_info['field'].replace('_', ' ').title()}**: {field_info['description']}\n"
            prompt += f"  Example: {field_info['example']}\n\n"
        
        prompt += "Please provide the missing information to enable accurate job ranking."
        return prompt
    
    def enhance_job_data(self, original_data: Dict[str, Any], additional_info: str) -> Dict[str, Any]:
        """Enhance existing job data with additional information provided by user."""
        # Use AI to intelligently merge the additional information
        prompt = ChatPromptTemplate.from_template("""
        You are an expert HR analyst with 15+ years of experience. I have existing job data and additional information provided by a user.
        
        Existing Job Data:
        {existing_data}
        
        Additional Information Provided by User:
        {additional_info}
        
        CRITICAL MERGING GUIDELINES:
        1. **Company Name**: ALWAYS keep as "Jman Group" (never change this)
        2. **Preserve Accuracy**: Keep existing accurate data, only enhance with new specific information
        3. **Be Specific**: Extract specific skills, responsibilities, and requirements from the additional info
        4. **No Generic Content**: Don't add generic or assumed information
        5. **Merge Intelligently**: Combine information logically without duplication
        6. **Industry**: Always set to "Software Development" (this is fixed)
        
        MERGING RULES:
        - For skills: Extract specific technical skills, tools, technologies mentioned
        - For responsibilities: Extract specific job duties and tasks mentioned
        - For experience level: Use the most specific level mentioned
        - For education: Use the most specific requirement mentioned
        - For location: Use the most specific location details mentioned
        - If additional info contradicts existing data, prefer the more specific information
        
        Respond with ONLY a valid JSON object containing all the required fields:
        {{
            "job_title": "exact job title",
            "company_name": "Jman Group",
            "industry": "Software Development",
            "experience_level": "entry/junior/mid/senior/lead/principal/executive",
            "required_skills": ["specific skill 1", "specific skill 2", "specific skill 3", "specific skill 4", "specific skill 5"],
            "preferred_skills": ["specific skill 1", "specific skill 2"],
            "key_responsibilities": ["specific responsibility 1", "specific responsibility 2", "specific responsibility 3", "specific responsibility 4"],
            "education_requirements": "specific education level and field",
            "location": "specific location details",
            "salary_range": "salary range if mentioned",
            "team_size": "team size if mentioned",
            "project_duration": "project timeline if mentioned"
        }}
        
        IMPORTANT: 
        - Return ONLY the JSON object, no additional text or explanations
        - Company name must always be "Jman Group"
        - Be extremely accurate and specific in extraction
        - Don't add generic or assumed content
        - Industry must always be "Software Development"
        """)
        
        chain = prompt | self.llm
        response = chain.invoke({
            "existing_data": json.dumps(original_data, indent=2),
            "additional_info": additional_info
        })
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            enhanced_data = json.loads(content)
            
            # Ensure company name is always set to Jman Group
            enhanced_data["company_name"] = "Jman Group"
            enhanced_data["industry"] = "Software Development"  # Always set to Software Development
            
            # Merge with original data, preferring enhanced data
            merged_data = {**original_data, **enhanced_data}
            
            # Final safety check for company name
            merged_data["company_name"] = "Jman Group"
            merged_data["industry"] = "Software Development"  # Always set to Software Development
            
            return merged_data
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error enhancing job data: {e}")
            return original_data

class JobMatcher:
    def __init__(self, db_path: str = "./chroma_db"):
        """Initialize the job matcher with vector database and Gemini AI LLM."""
        self.db_path = db_path
        
        # Use Google's Gemini AI embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Use Google's Gemini AI for LLM interactions
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )
        
        # Initialize job data extractor
        self.job_extractor = JobDataExtractor(self.llm)
        
        # Initialize vector store
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """Initialize the vector store with proper ChromaDB settings."""
        try:
            if not os.path.exists(self.db_path):
                raise ValueError(f"Vector database not found at {self.db_path}. Please add resumes first.")
            
            # Create client settings with comprehensive telemetry suppression
            client_settings = chromadb.config.Settings(
                anonymized_telemetry=False,
                is_persistent=True,
                allow_reset=True
            )
            
            # Initialize vector store
            self.vectorstore = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings,
                client_settings=client_settings
            )
            
            print(f"Job matcher vector store initialized successfully at {self.db_path}")
            
        except Exception as e:
            print(f"Error initializing job matcher vector store: {e}")
            raise ValueError(f"Vector database not found at {self.db_path}. Please add resumes first.")
    
    def extract_job_requirements(self, job_description: str) -> Dict[str, Any]:
        """Extract key requirements and skills from job description using Gemini AI."""
        # Use the new comprehensive job data extractor
        job_data = self.job_extractor.extract_job_data(job_description)
        return job_data
    
    def validate_job_description(self, job_description: str) -> Dict[str, Any]:
        """Validate job description and identify missing required information."""
        # Extract job data
        job_data = self.job_extractor.extract_job_data(job_description)
        
        # Validate the extracted data
        validation_result = self.job_extractor.validate_job_data(job_data)
        
        return {
            "job_data": job_data,
            "validation": validation_result
        }
    
    def enhance_job_description(self, original_description: str, additional_info: str) -> Dict[str, Any]:
        """Enhance job description with additional information and re-validate."""
        # Get current job data
        current_data = self.job_extractor.extract_job_data(original_description)
        
        # Enhance with additional information
        enhanced_data = self.job_extractor.enhance_job_data(current_data, additional_info)
        
        # Re-validate
        validation_result = self.job_extractor.validate_job_data(enhanced_data)
        
        return {
            "job_data": enhanced_data,
            "validation": validation_result,
            "original_description": original_description,
            "additional_info": additional_info
        }
    
    def rank_resumes(self, job_description: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Rank resumes based on job description similarity and relevance using Gemini AI."""
        # First validate that we have complete job data
        validation_result = self.validate_job_description(job_description)
        
        if not validation_result["validation"]["is_complete"]:
            raise ValueError(
                f"Incomplete job description. Missing required fields: "
                f"{[f['field'] for f in validation_result['validation']['missing_fields']]}. "
                f"Completeness score: {validation_result['validation']['completeness_score']}%"
            )
        
        # Extract job requirements from validated data
        job_requirements = validation_result["job_data"]
        
        # Search for similar resumes
        similar_docs = self.vectorstore.similarity_search_with_score(
            job_description,
            k=top_k * 2  # Get more candidates for better ranking
        )
        
        # Group by candidate and calculate average similarity
        candidate_scores = {}
        for doc, score in similar_docs:
            candidate_name = doc.metadata.get("candidate_name", "Unknown")
            candidate_id = doc.metadata.get("candidate_id", candidate_name)
            
            if candidate_id not in candidate_scores:
                candidate_scores[candidate_id] = {
                    "name": candidate_name,
                    "id": candidate_id,
                    "scores": [],
                    "content": [],
                    "metadata": doc.metadata  # Store metadata for contact info
                }
            
            candidate_scores[candidate_id]["scores"].append(score)
            candidate_scores[candidate_id]["content"].append(doc.page_content)
        
        # Calculate average scores and prepare for detailed analysis
        ranked_candidates = []
        for candidate_id, data in candidate_scores.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            full_content = " ".join(data["content"])
            
            # Extract contact information from metadata
            metadata = data["metadata"]
            contact_info = {
                "email": metadata.get("email", ""),
                "phone": metadata.get("phone", ""),
                "linkedin": metadata.get("linkedin", ""),
                "github": metadata.get("github", ""),
                "portfolio": metadata.get("portfolio", ""),
                "location": metadata.get("location", "")
            }
            
            # Convert string metadata back to lists for analysis
            def convert_metadata_back(value):
                """Convert string metadata back to appropriate types for analysis."""
                if isinstance(value, str) and ';' in value:
                    return [item.strip() for item in value.split(';') if item.strip()]
                elif isinstance(value, str) and value:
                    return [value]
                elif isinstance(value, list):
                    return value
                else:
                    return []
            
            ranked_candidates.append({
                "candidate_id": candidate_id,
                "candidate_name": data["name"],
                "similarity_score": avg_score,
                "content": full_content,
                "job_requirements": job_requirements,
                "contact_info": contact_info,
                "skills": convert_metadata_back(metadata.get("skills", "")),
                "languages": convert_metadata_back(metadata.get("languages", "")),
                "frameworks": convert_metadata_back(metadata.get("frameworks", "")),
                "tools": convert_metadata_back(metadata.get("tools", "")),
                "experience_years": metadata.get("experience_years", 0),
                "education_level": metadata.get("education_level", "Unknown")
            })
        
        # Sort by similarity score (lower is better for distance)
        ranked_candidates.sort(key=lambda x: x["similarity_score"])
        
        # Get top candidates for detailed analysis
        top_candidates = ranked_candidates[:top_k]
        
        # Perform detailed analysis using Gemini AI
        detailed_rankings = self._analyze_candidate_fit(top_candidates, job_description)
        
        return detailed_rankings
    
    def _analyze_candidate_fit(self, candidates: List[Dict], job_description: str) -> List[Dict]:
        """Perform detailed analysis of candidate fit using Gemini AI with enhanced reasoning."""
        detailed_rankings = []
        
        for i, candidate in enumerate(candidates):
            # Convert string metadata back to lists for analysis
            def convert_metadata_back(value):
                """Convert string metadata back to appropriate types for analysis."""
                if isinstance(value, str) and ';' in value:
                    return [item.strip() for item in value.split(';') if item.strip()]
                elif isinstance(value, str) and value:
                    return [value]
                elif isinstance(value, list):
                    return value
                else:
                    return []
            
            # Extract and convert metadata
            candidate_skills = convert_metadata_back(candidate.get("skills", ""))
            candidate_languages = convert_metadata_back(candidate.get("languages", ""))
            candidate_frameworks = convert_metadata_back(candidate.get("frameworks", ""))
            candidate_tools = convert_metadata_back(candidate.get("tools", ""))
            
            analysis_prompt = ChatPromptTemplate.from_template("""
            You are an expert HR recruiter analyzing candidate fit for a job position.
            
            Job Description:
            {job_description}
            
            Candidate Resume:
            {resume_content}
            
            Job Requirements:
            {job_requirements}
            
            Candidate Skills Analysis:
            - Programming Languages: {candidate_languages}
            - Frameworks: {candidate_frameworks}
            - Tools: {candidate_tools}
            - All Skills: {candidate_skills}
            
            Analyze the candidate's fit and respond with ONLY a valid JSON object:
            {{
                "overall_fit_score": 85,
                "strengths": ["strength1", "strength2", "strength3"],
                "weaknesses": ["weakness1", "weakness2"],
                "missing_skills": ["skill1", "skill2"],
                "recommendation": "strong_fit",
                "reasoning": "Detailed explanation of why this candidate is a good fit or not",
                "rank_reason": "Specific reason why this candidate deserves this rank",
                "key_matches": ["match1", "match2", "match3"],
                "improvement_areas": ["area1", "area2"],
                "technical_expertise": "high/medium/low",
                "experience_relevance": "high/medium/low",
                "skill_alignment": "high/medium/low",
                "culture_fit": "high/medium/low",
                "growth_potential": "high/medium/low"
            }}
            
            Scoring guidelines:
            - overall_fit_score: 0-100 (higher is better)
            - recommendation: "strong_fit" (90-100), "good_fit" (70-89), "partial_fit" (50-69), "weak_fit" (0-49)
            - strengths: List specific skills/experiences that match the job
            - weaknesses: List areas where candidate lacks experience
            - missing_skills: List required skills not found in resume
            - reasoning: 2-3 sentences explaining the assessment
            - rank_reason: Specific reason why this candidate deserves this particular rank
            - key_matches: Top 3 specific matches between candidate and job requirements
            - improvement_areas: Areas where candidate could improve for this role
            - technical_expertise: Assess technical skill level (high/medium/low)
            - experience_relevance: Assess how relevant their experience is (high/medium/low)
            - skill_alignment: Assess how well their skills align with requirements (high/medium/low)
            - culture_fit: Assess potential cultural fit (high/medium/low)
            - growth_potential: Assess potential for growth in the role (high/medium/low)
            
            IMPORTANT: Return ONLY the JSON object, no additional text or explanations.
            """)
            
            chain = analysis_prompt | self.llm
            response = chain.invoke({
                "job_description": job_description,
                "resume_content": candidate["content"][:3000],  # Limit content length
                "job_requirements": json.dumps(candidate["job_requirements"]),
                "candidate_languages": ', '.join(candidate_languages),
                "candidate_frameworks": ', '.join(candidate_frameworks),
                "candidate_tools": ', '.join(candidate_tools),
                "candidate_skills": ', '.join(candidate_skills)
            })
            
            try:
                # Clean the response to extract JSON
                content = response.content.strip()
                # Remove any markdown formatting
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                analysis = json.loads(content)
                
                # Validate and set defaults for missing fields
                fit_score = analysis.get("overall_fit_score", 50)
                if not isinstance(fit_score, int) or fit_score < 0 or fit_score > 100:
                    fit_score = 50
                
                recommendation = analysis.get("recommendation", "unknown")
                if recommendation not in ["strong_fit", "good_fit", "partial_fit", "weak_fit"]:
                    if fit_score >= 90:
                        recommendation = "strong_fit"
                    elif fit_score >= 70:
                        recommendation = "good_fit"
                    elif fit_score >= 50:
                        recommendation = "partial_fit"
                    else:
                        recommendation = "weak_fit"
                
                detailed_rankings.append({
                    "rank": i + 1,
                    "candidate_id": candidate["candidate_id"],
                    "candidate_name": candidate["candidate_name"],
                    "similarity_score": candidate["similarity_score"],
                    "fit_score": fit_score,
                    "strengths": analysis.get("strengths", []),
                    "weaknesses": analysis.get("weaknesses", []),
                    "missing_skills": analysis.get("missing_skills", []),
                    "recommendation": recommendation,
                    "reasoning": analysis.get("reasoning", "Analysis completed"),
                    "rank_reason": analysis.get("rank_reason", "Ranked based on fit score"),
                    "key_matches": analysis.get("key_matches", []),
                    "improvement_areas": analysis.get("improvement_areas", []),
                    "technical_expertise": analysis.get("technical_expertise", "medium"),
                    "experience_relevance": analysis.get("experience_relevance", "medium"),
                    "skill_alignment": analysis.get("skill_alignment", "medium"),
                    "culture_fit": analysis.get("culture_fit", "medium"),
                    "growth_potential": analysis.get("growth_potential", "medium"),
                    "content_preview": candidate["content"][:500] + "...",
                    "email": candidate.get("contact_info", {}).get("email"),
                    "phone": candidate.get("contact_info", {}).get("phone"),
                    "linkedin": candidate.get("contact_info", {}).get("linkedin"),
                    "github": candidate.get("contact_info", {}).get("github"),
                    "portfolio": candidate.get("contact_info", {}).get("portfolio"),
                    "location": candidate.get("contact_info", {}).get("location"),
                    "skills": candidate_skills,
                    "languages": candidate_languages,
                    "frameworks": candidate_frameworks,
                    "tools": candidate_tools
                })
                
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error analyzing candidate {candidate['candidate_name']}: {e}")
                print(f"Raw response: {response.content}")
                
                # Calculate a basic fit score based on similarity
                similarity_score = candidate["similarity_score"]
                basic_fit_score = max(0, min(100, int((1 - similarity_score) * 100)))
                
                # Determine recommendation based on fit score
                if basic_fit_score >= 90:
                    recommendation = "strong_fit"
                elif basic_fit_score >= 70:
                    recommendation = "good_fit"
                elif basic_fit_score >= 50:
                    recommendation = "partial_fit"
                else:
                    recommendation = "weak_fit"
                
                detailed_rankings.append({
                    "rank": i + 1,
                    "candidate_id": candidate["candidate_id"],
                    "candidate_name": candidate["candidate_name"],
                    "similarity_score": candidate["similarity_score"],
                    "fit_score": basic_fit_score,
                    "strengths": ["Resume content matches job requirements"],
                    "weaknesses": ["Detailed analysis unavailable"],
                    "missing_skills": [],
                    "recommendation": recommendation,
                    "reasoning": f"Basic analysis based on similarity score. Fit score: {basic_fit_score}/100",
                    "rank_reason": f"Ranked {i+1} based on similarity score analysis",
                    "key_matches": ["Content similarity"],
                    "improvement_areas": ["Detailed analysis needed"],
                    "technical_expertise": "medium",
                    "experience_relevance": "medium",
                    "skill_alignment": "medium",
                    "culture_fit": "medium",
                    "growth_potential": "medium",
                    "content_preview": candidate["content"][:500] + "...",
                    "email": candidate.get("contact_info", {}).get("email"),
                    "phone": candidate.get("contact_info", {}).get("phone"),
                    "linkedin": candidate.get("contact_info", {}).get("linkedin"),
                    "github": candidate.get("contact_info", {}).get("github"),
                    "portfolio": candidate.get("contact_info", {}).get("portfolio"),
                    "location": candidate.get("contact_info", {}).get("location"),
                    "skills": candidate_skills,
                    "languages": candidate_languages,
                    "frameworks": candidate_frameworks,
                    "tools": candidate_tools
                })
        
        # Re-rank based on fit score
        detailed_rankings.sort(key=lambda x: x["fit_score"], reverse=True)
        
        # Update ranks
        for i, candidate in enumerate(detailed_rankings):
            candidate["rank"] = i + 1
        
        return detailed_rankings
    
    def get_candidate_details(self, candidate_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific candidate."""
        docs = self.vectorstore.similarity_search(
            f"candidate {candidate_id}",
            k=10,
            filter={"candidate_id": candidate_id}
        )
        
        if not docs:
            return {"error": "Candidate not found"}
        
        full_content = " ".join([doc.page_content for doc in docs])
        candidate_name = docs[0].metadata.get("candidate_name", "Unknown")
        
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "full_resume": full_content,
            "chunks_count": len(docs)
        } 