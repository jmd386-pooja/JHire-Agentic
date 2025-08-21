import os
import json
import re
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import chromadb
import chromadb.config
from dotenv import load_dotenv
import time
import shutil

load_dotenv()

# Disable ChromaDB telemetry completely at the system level
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["ALLOW_RESET"] = "TRUE"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "FALSE"
os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "FALSE"

# Disable telemetry at the module level
chromadb.config.Settings.anonymized_telemetry = False

class ResumeData(BaseModel):
    """Structured data model for extracted resume information."""
    # Personal Information
    full_name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    location: str = Field(description="City, State, Country or similar location")
    
    # Professional Links
    linkedin: str = Field(description="LinkedIn profile URL")
    github: str = Field(description="GitHub profile URL")
    portfolio: str = Field(description="Portfolio or personal website URL")
    
    # Skills & Technologies
    programming_languages: List[str] = Field(description="Programming languages (Python, Java, etc.)")
    frameworks: List[str] = Field(description="Frameworks and libraries (React, Django, etc.)")
    databases: List[str] = Field(description="Databases and data stores (MySQL, MongoDB, etc.)")
    cloud_platforms: List[str] = Field(description="Cloud platforms (AWS, Azure, GCP, etc.)")
    devops_tools: List[str] = Field(description="DevOps tools (Docker, Kubernetes, Jenkins, etc.)")
    other_technologies: List[str] = Field(description="Other technologies, tools, and platforms")
    
    # Experience & Education
    total_experience_years: float = Field(description="Total years of professional experience")
    education_level: str = Field(description="Highest education level (Bachelor's, Master's, PhD, etc.)")
    degree_field: str = Field(description="Field of study (Computer Science, Engineering, etc.)")
    
    # Languages & Communication
    spoken_languages: List[str] = Field(description="Spoken languages (English, Spanish, etc.)")
    
    # Certifications
    certifications: List[str] = Field(description="Professional certifications")
    
    # Summary
    professional_summary: str = Field(description="Brief professional summary or objective")
    
    # Key Achievements
    key_achievements: List[str] = Field(description="Notable professional achievements")
    
    # Work Style & Preferences
    work_preferences: List[str] = Field(description="Work preferences (Remote, On-site, Hybrid, etc.)")
    
    # Industry Experience
    industries: List[str] = Field(description="Industries worked in (Technology, Finance, Healthcare, etc.)")

class AIResumeExtractor:
    """AI-powered resume information extractor using Gemini AI."""
    
    def __init__(self):
        """Initialize the AI extractor with Gemini AI."""
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
            max_output_tokens=4000
        )
        
        self.parser = PydanticOutputParser(pydantic_object=ResumeData)
        
        # Comprehensive prompt for resume extraction
        self.extraction_prompt = PromptTemplate(
            input_variables=["resume_text"],
            template="""
You are an expert AI agent specialized in extracting comprehensive information from resumes. 
Your task is to analyze the provided resume text and extract all relevant information in a structured format.

IMPORTANT INSTRUCTIONS:
1. Extract ALL available information - be thorough and comprehensive
2. If information is not explicitly stated, use context clues and reasonable inference
3. For missing fields, use "Not specified" or empty lists as appropriate
4. Normalize and standardize extracted information
5. Ensure all extracted data is accurate and relevant

RESUME TEXT:
{resume_text}

Please extract the following information and format it according to the ResumeData schema:

1. **Personal Information**: Name, email, phone, location
2. **Professional Links**: LinkedIn, GitHub, portfolio/website
3. **Technical Skills**: Programming languages, frameworks, databases, cloud platforms, DevOps tools
4. **Experience & Education**: Years of experience, education level, field of study
5. **Languages & Communication**: Spoken languages
6. **Certifications**: Professional certifications
7. **Professional Summary**: Brief summary or objective
8. **Key Achievements**: Notable professional accomplishments
9. **Work Preferences**: Remote/on-site preferences if mentioned
10. **Industry Experience**: Industries worked in

Be thorough and extract every piece of relevant information you can find. Use context clues when information is implied but not explicitly stated.

{format_instructions}
"""
        )
    
    def extract_resume_data(self, resume_text: str) -> ResumeData:
        """Extract comprehensive resume data using AI."""
        try:
            print("🤖 AI Agent analyzing resume content...")
            
            # Format the prompt with parser instructions
            formatted_prompt = self.extraction_prompt.format(
                resume_text=resume_text,
                format_instructions=self.parser.get_format_instructions()
            )
            
            # Get AI response
            response = self.llm.invoke(formatted_prompt)
            
            # Parse the response
            extracted_data = self.parser.parse(response.content)
            
            print("✅ AI extraction completed successfully")
            return extracted_data
            
        except Exception as e:
            print(f"❌ AI extraction failed: {e}")
            # Fallback to basic extraction
            return self._fallback_extraction(resume_text)
    
    def _fallback_extraction(self, resume_text: str) -> ResumeData:
        """Fallback extraction method using basic patterns if AI fails."""
        print("⚠️ Using fallback extraction method...")
        
        # Basic email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, resume_text)
        email = email_match.group(0) if email_match else "Not specified"
        
        # Basic phone extraction
        phone_pattern = r'[\+]?[1-9][\d]{0,15}'
        phone_match = re.search(phone_pattern, resume_text)
        phone = phone_match.group(0) if phone_match else "Not specified"
        
        # Basic name extraction (first line that looks like a name)
        lines = resume_text.split('\n')
        name = "Not specified"
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if (len(line) > 2 and len(line) < 50 and 
                not line.lower().startswith(('email', 'phone', 'linkedin', 'github', 'objective', 'summary')) and
                not re.search(r'[0-9]', line) and
                re.search(r'[A-Za-z]', line)):
                name = line
                break
        
        return ResumeData(
            full_name=name,
            email=email,
            phone=phone,
            location="Not specified",
            linkedin="Not specified",
            github="Not specified",
            portfolio="Not specified",
            programming_languages=[],
            frameworks=[],
            databases=[],
            cloud_platforms=[],
            devops_tools=[],
            other_technologies=[],
            total_experience_years=0.0,
            education_level="Not specified",
            degree_field="Not specified",
            spoken_languages=[],
            certifications=[],
            professional_summary="Not specified",
            key_achievements=[],
            work_preferences=[],
            industries=[]
        )

class AIResumeProcessor:
    """Enhanced resume processor with AI-powered information extraction."""
    
    def __init__(self, db_path: str = "./chroma_db"):
        """Initialize the AI resume processor with vector database."""
        self.db_path = db_path
        
        # Initialize AI extractor
        self.ai_extractor = AIResumeExtractor()
        
        # Use Google's Gemini AI embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Initialize vector store with proper settings
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """Initialize the vector store with proper ChromaDB settings."""
        try:
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
            
            print(f"Vector store initialized successfully at {self.db_path}")
            
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            # Create a fresh instance with telemetry disabled
            self.vectorstore = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings,
                client_settings=chromadb.config.Settings(
                    anonymized_telemetry=False,
                    is_persistent=True,
                    allow_reset=True
                )
            )
    
    def process_resume(self, resume_text: str, candidate_name: str, candidate_id: str = None) -> str:
        """Process a single resume using AI-powered extraction and add it to the vector database."""
        try:
            print(f"\n🔍 AI-POWERED RESUME PROCESSING FOR: {candidate_name}")
            print("=" * 60)
            
            # Use AI agent to extract comprehensive information
            print("🤖 AI Agent extracting resume information...")
            extracted_data = self.ai_extractor.extract_resume_data(resume_text)
            
            # Print extracted information summary
            self._print_extraction_summary(extracted_data)
            
            # Convert list metadata to strings for ChromaDB compatibility
            def convert_metadata_value(value):
                """Convert metadata values to ChromaDB-compatible types."""
                if isinstance(value, list):
                    return '; '.join(str(item) for item in value) if value else ''
                elif value is None:
                    return ''
                else:
                    return str(value)
            
            # Create document with comprehensive AI-extracted metadata
            doc = Document(
                page_content=resume_text,
                metadata={
                    "candidate_name": candidate_name,
                    "candidate_id": candidate_id or candidate_name,
                    "type": "resume",
                    "timestamp": time.time(),
                    
                    # AI-extracted contact information
                    "email": extracted_data.email,
                    "phone": extracted_data.phone,
                    "linkedin": extracted_data.linkedin,
                    "github": extracted_data.github,
                    "portfolio": extracted_data.portfolio,
                    "location": extracted_data.location,
                    
                    # AI-extracted skills and technologies
                    "programming_languages": convert_metadata_value(extracted_data.programming_languages),
                    "frameworks": convert_metadata_value(extracted_data.frameworks),
                    "databases": convert_metadata_value(extracted_data.databases),
                    "cloud_platforms": convert_metadata_value(extracted_data.cloud_platforms),
                    "devops_tools": convert_metadata_value(extracted_data.devops_tools),
                    "other_technologies": convert_metadata_value(extracted_data.other_technologies),
                    
                    # AI-extracted experience and education
                    "total_experience_years": extracted_data.total_experience_years,
                    "education_level": extracted_data.education_level,
                    "degree_field": extracted_data.degree_field,
                    
                    # AI-extracted additional information
                    "spoken_languages": convert_metadata_value(extracted_data.spoken_languages),
                    "certifications": convert_metadata_value(extracted_data.certifications),
                    "professional_summary": extracted_data.professional_summary,
                    "key_achievements": convert_metadata_value(extracted_data.key_achievements),
                    "work_preferences": convert_metadata_value(extracted_data.work_preferences),
                    "industries": convert_metadata_value(extracted_data.industries),
                    
                    # Legacy fields for backward compatibility
                    "skills": convert_metadata_value(extracted_data.programming_languages + 
                                                   extracted_data.frameworks + 
                                                   extracted_data.databases + 
                                                   extracted_data.cloud_platforms + 
                                                   extracted_data.devops_tools + 
                                                   extracted_data.other_technologies),
                    "experience_years": extracted_data.total_experience_years,
                    "languages": convert_metadata_value(extracted_data.spoken_languages),
                    "tools": convert_metadata_value(extracted_data.devops_tools + extracted_data.other_technologies)
                }
            )
            
            # Split the document into chunks
            chunks = self.text_splitter.split_documents([doc])
            
            # Add to vector store
            self.vectorstore.add_documents(chunks)
            self.vectorstore.persist()
            
            print(f"\n✅ SUCCESSFULLY PROCESSED RESUME WITH AI")
            print(f"   Candidate: {candidate_name}")
            print(f"   Content Length: {len(resume_text)} characters")
            print(f"   Chunks Created: {len(chunks)}")
            print(f"   AI-Extracted Fields: {self._count_extracted_fields(extracted_data)}/25 fields")
            print(f"   Total Skills Found: {len(extracted_data.programming_languages + extracted_data.frameworks + extracted_data.databases + extracted_data.cloud_platforms + extracted_data.devops_tools + extracted_data.other_technologies)}")
            
            return f"AI-processed resume for {candidate_name} ({len(chunks)} chunks, {self._count_extracted_fields(extracted_data)}/25 fields extracted)"
            
        except Exception as e:
            print(f"❌ Error processing resume for {candidate_name}: {e}")
            raise e
    
    def _print_extraction_summary(self, extracted_data: ResumeData):
        """Print a comprehensive summary of AI-extracted information."""
        print(f"\n📋 AI EXTRACTION SUMMARY:")
        print(f"   👤 Personal Info:")
        print(f"      • Name: {extracted_data.full_name}")
        print(f"      • Email: {extracted_data.email}")
        print(f"      • Phone: {extracted_data.phone}")
        print(f"      • Location: {extracted_data.location}")
        
        print(f"   🔗 Professional Links:")
        print(f"      • LinkedIn: {extracted_data.linkedin}")
        print(f"      • GitHub: {extracted_data.github}")
        print(f"      • Portfolio: {extracted_data.portfolio}")
        
        print(f"   💻 Technical Skills:")
        print(f"      • Programming Languages: {', '.join(extracted_data.programming_languages) if extracted_data.programming_languages else 'None'}")
        print(f"      • Frameworks: {', '.join(extracted_data.frameworks) if extracted_data.frameworks else 'None'}")
        print(f"      • Databases: {', '.join(extracted_data.databases) if extracted_data.databases else 'None'}")
        print(f"      • Cloud Platforms: {', '.join(extracted_data.cloud_platforms) if extracted_data.cloud_platforms else 'None'}")
        print(f"      • DevOps Tools: {', '.join(extracted_data.devops_tools) if extracted_data.devops_tools else 'None'}")
        print(f"      • Other Technologies: {', '.join(extracted_data.other_technologies) if extracted_data.other_technologies else 'None'}")
        
        print(f"   🎓 Education & Experience:")
        print(f"      • Experience: {extracted_data.total_experience_years} years")
        print(f"      • Education: {extracted_data.education_level}")
        print(f"      • Field: {extracted_data.degree_field}")
        
        print(f"   🌍 Languages & Certifications:")
        print(f"      • Spoken Languages: {', '.join(extracted_data.spoken_languages) if extracted_data.spoken_languages else 'None'}")
        print(f"      • Certifications: {', '.join(extracted_data.certifications) if extracted_data.certifications else 'None'}")
        
        print(f"   🏆 Achievements & Preferences:")
        print(f"      • Key Achievements: {len(extracted_data.key_achievements)} found")
        print(f"      • Work Preferences: {', '.join(extracted_data.work_preferences) if extracted_data.work_preferences else 'None'}")
        print(f"      • Industries: {', '.join(extracted_data.industries) if extracted_data.industries else 'None'}")
    
    def _count_extracted_fields(self, extracted_data: ResumeData) -> int:
        """Count how many fields were successfully extracted."""
        count = 0
        
        # Count non-empty fields
        if extracted_data.full_name and extracted_data.full_name != "Not specified":
            count += 1
        if extracted_data.email and extracted_data.email != "Not specified":
            count += 1
        if extracted_data.phone and extracted_data.phone != "Not specified":
            count += 1
        if extracted_data.location and extracted_data.location != "Not specified":
            count += 1
        if extracted_data.linkedin and extracted_data.linkedin != "Not specified":
            count += 1
        if extracted_data.github and extracted_data.github != "Not specified":
            count += 1
        if extracted_data.portfolio and extracted_data.portfolio != "Not specified":
            count += 1
        
        # Count skills and technologies
        if extracted_data.programming_languages:
            count += 1
        if extracted_data.frameworks:
            count += 1
        if extracted_data.databases:
            count += 1
        if extracted_data.cloud_platforms:
            count += 1
        if extracted_data.devops_tools:
            count += 1
        if extracted_data.other_technologies:
            count += 1
        
        # Count other fields
        if extracted_data.total_experience_years > 0:
            count += 1
        if extracted_data.education_level and extracted_data.education_level != "Not specified":
            count += 1
        if extracted_data.degree_field and extracted_data.degree_field != "Not specified":
            count += 1
        if extracted_data.spoken_languages:
            count += 1
        if extracted_data.certifications:
            count += 1
        if extracted_data.professional_summary and extracted_data.professional_summary != "Not specified":
            count += 1
        if extracted_data.key_achievements:
            count += 1
        if extracted_data.work_preferences:
            count += 1
        if extracted_data.industries:
            count += 1
        
        return count
    
    def get_total_resumes(self) -> int:
        """Get the total number of resumes in the database."""
        try:
            if not hasattr(self, 'vectorstore') or not self.vectorstore:
                return 0
            
            if not hasattr(self.vectorstore, '_collection') or not self.vectorstore._collection:
                return 0
            
            try:
                collection_count = self.vectorstore._collection.count()
                if collection_count == 0:
                    return 0
            except Exception as e:
                print(f"Error getting collection count: {e}")
                return 0
            
            try:
                results = self.vectorstore._collection.get()
                
                if not results or not results.get('metadatas'):
                    return 0
                
                unique_candidates = set()
                for metadata in results['metadatas']:
                    if metadata:
                        candidate_id = metadata.get("candidate_id", "Unknown")
                        unique_candidates.add(candidate_id)
                
                return len(unique_candidates)
                
            except Exception as e:
                print(f"Error getting documents for counting: {e}")
                return 0
            
        except Exception as e:
            print(f"Error getting total resumes: {e}")
            return 0
    
    def get_all_candidates(self) -> List[Dict[str, Any]]:
        """Get all candidates with their AI-extracted resume information."""
        try:
            if not hasattr(self, 'vectorstore') or not self.vectorstore:
                return []
            
            if not hasattr(self.vectorstore, '_collection') or not self.vectorstore._collection:
                return []
            
            try:
                collection_count = self.vectorstore._collection.count()
                if collection_count == 0:
                    return []
            except Exception as e:
                print(f"Error getting collection count: {e}")
                return []
            
            try:
                results = self.vectorstore._collection.get()
                
                if not results or not results.get('documents'):
                    return []
                
                candidates = {}
                documents = results['documents']
                metadatas = results['metadatas']
                
                for i, doc_content in enumerate(documents):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    candidate_id = metadata.get("candidate_id", "Unknown")
                    candidate_name = metadata.get("candidate_name", "Unknown")
                    
                    if candidate_id not in candidates:
                        candidates[candidate_id] = {
                            "name": candidate_name,
                            "id": candidate_id,
                            "content": [],
                            "chunks": 0,
                            "email": metadata.get("email"),
                            "phone": metadata.get("phone"),
                            "linkedin": metadata.get("linkedin"),
                            "github": metadata.get("github"),
                            "portfolio": metadata.get("portfolio"),
                            "location": metadata.get("location"),
                            "programming_languages": metadata.get("programming_languages", ""),
                            "frameworks": metadata.get("frameworks", ""),
                            "databases": metadata.get("databases", ""),
                            "cloud_platforms": metadata.get("cloud_platforms", ""),
                            "devops_tools": metadata.get("devops_tools", ""),
                            "other_technologies": metadata.get("other_technologies", ""),
                            "total_experience_years": metadata.get("total_experience_years", 0),
                            "education_level": metadata.get("education_level", ""),
                            "degree_field": metadata.get("degree_field", ""),
                            "spoken_languages": metadata.get("spoken_languages", ""),
                            "certifications": metadata.get("certifications", ""),
                            "professional_summary": metadata.get("professional_summary", ""),
                            "key_achievements": metadata.get("key_achievements", ""),
                            "work_preferences": metadata.get("work_preferences", ""),
                            "industries": metadata.get("industries", "")
                        }
                    
                    candidates[candidate_id]["content"].append(doc_content)
                    candidates[candidate_id]["chunks"] += 1
                
                return list(candidates.values())
                
            except Exception as e:
                print(f"Error getting documents for candidates: {e}")
                return []
            
        except Exception as e:
            print(f"Error getting all candidates: {e}")
            return []
    
    def clear_database(self):
        """Clear all data from the vector database."""
        print(f"Clearing database at: {self.db_path}")
        
        try:
            try:
                results = self.vectorstore._collection.get()
                if results and results['ids']:
                    print(f"Deleting {len(results['ids'])} documents...")
                    self.vectorstore._collection.delete(ids=results['ids'])
                    print("Successfully deleted all documents")
            except Exception as e:
                print(f"Error deleting documents: {e}")
            
            try:
                collection_name = self.vectorstore._collection.name
                self.vectorstore._client.delete_collection(collection_name)
                print(f"Deleted collection: {collection_name}")
            except Exception as e:
                print(f"Error deleting collection: {e}")
            
            time.sleep(2)
            if os.path.exists(self.db_path):
                try:
                    shutil.rmtree(self.db_path)
                    print(f"Removed database directory: {self.db_path}")
                except Exception as e:
                    print(f"Error removing directory: {e}")
            
            self._initialize_vectorstore()
            print("Database cleared and reinitialized")
            
        except Exception as e:
            print(f"Error in clear_database: {e}")
            self._initialize_vectorstore()
    
    def force_clear_database(self):
        """Force clear the database."""
        print("Force clearing database...")
        
        try:
            try:
                self.vectorstore._client.reset()
            except:
                pass
            
            time.sleep(3)
            
            if os.path.exists(self.db_path):
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        shutil.rmtree(self.db_path)
                        print(f"Force removed database directory")
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(3)
                        else:
                            print("Failed to remove directory after retries")
                    except Exception as e:
                        print(f"Error removing directory: {e}")
                        break
            
            self._initialize_vectorstore()
            print("Database force cleared and reinitialized")
            
        except Exception as e:
            print(f"Error in force_clear_database: {e}")
            self._initialize_vectorstore()
    
    def reset_database(self):
        """Complete database reset."""
        print("Performing complete database reset...")
        
        try:
            try:
                self.vectorstore._client.reset()
            except:
                pass
            
            time.sleep(5)
            
            if os.path.exists(self.db_path):
                max_retries = 10
                for attempt in range(max_retries):
                    try:
                        for root, dirs, files in os.walk(self.db_path, topdown=False):
                            for file in files:
                                try:
                                    os.remove(os.path.join(root, file))
                                except:
                                    pass
                            for dir in dirs:
                                try:
                                    os.rmdir(os.path.join(root, dir))
                                except:
                                    pass
                        
                        shutil.rmtree(self.db_path)
                        print("Successfully removed database directory")
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(5)
                        else:
                            print("Failed to remove directory after retries")
                    except Exception as e:
                        print(f"Error removing directory: {e}")
                        break
            
            self._initialize_vectorstore()
            print("Database completely reset and reinitialized")
            
        except Exception as e:
            print(f"Error in reset_database: {e}")
            self._initialize_vectorstore()
