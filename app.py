import streamlit as st
import pandas as pd
import json
from typing import List, Dict, Any
import os
import warnings
from resume_processor import ResumeProcessor
from job_matcher import JobMatcher
from email_service import EmailService
from dotenv import load_dotenv

# Suppress ChromaDB telemetry warnings
warnings.filterwarnings("ignore", message=".*Failed to send telemetry event.*")
warnings.filterwarnings("ignore", message=".*capture.*takes 1 positional argument but 3 were given.*")

# Disable ChromaDB telemetry comprehensively
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"
os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "false"
os.environ["ALLOW_RESET"] = "true"

# Load environment variables after setting ChromaDB config
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Agentic AI Resume Matcher (Gemini AI)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .candidate-card {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }
    .fit-score {
        font-size: 1.5rem;
        font-weight: bold;
    }
    .strength-tag {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        margin: 0.25rem;
        display: inline-block;
    }
    .weakness-tag {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        margin: 0.25rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'resume_processor' not in st.session_state:
    st.session_state.resume_processor = ResumeProcessor()
if 'job_matcher' not in st.session_state:
    try:
        st.session_state.job_matcher = JobMatcher()
    except ValueError:
        st.session_state.job_matcher = None
if 'email_service' not in st.session_state:
    st.session_state.email_service = EmailService()

def extract_text_from_file(uploaded_file):
    """Extract text from uploaded file based on file type with enhanced PDF processing."""
    file_extension = uploaded_file.name.lower().split('.')[-1]
    
    try:
        if file_extension == 'txt':
            # Try different encodings for text files
            content = uploaded_file.read()
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            # If all encodings fail, use latin-1 as fallback
            return content.decode('latin-1', errors='ignore')
        
        elif file_extension == 'pdf':
            # Enhanced PDF text extraction using multiple methods
            try:
                # Method 1: Try PyPDF2 first
                try:
                    import PyPDF2
                    uploaded_file.seek(0)  # Reset file pointer
                    pdf_reader = PyPDF2.PdfReader(uploaded_file)
                    text = ""
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    
                    if text.strip():
                        print(f"✅ PyPDF2 successfully extracted {len(text)} characters")
                        return text.strip()
                    else:
                        print("⚠️ PyPDF2 extracted empty text, trying alternative method")
                except Exception as e:
                    print(f"⚠️ PyPDF2 failed: {e}, trying alternative method")
                
                # Method 2: Try pdfplumber for better text extraction
                try:
                    import pdfplumber
                    uploaded_file.seek(0)  # Reset file pointer
                    with pdfplumber.open(uploaded_file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        
                        if text.strip():
                            print(f"✅ pdfplumber successfully extracted {len(text)} characters")
                            return text.strip()
                        else:
                            print("⚠️ pdfplumber extracted empty text, trying alternative method")
                except ImportError:
                    print("⚠️ pdfplumber not available, trying alternative method")
                except Exception as e:
                    print(f"⚠️ pdfplumber failed: {e}, trying alternative method")
                
                # Method 3: Try pymupdf (fitz) for advanced text extraction
                try:
                    import fitz  # PyMuPDF
                    uploaded_file.seek(0)  # Reset file pointer
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    text = ""
                    for page in doc:
                        page_text = page.get_text()
                        if page_text:
                            text += page_text + "\n"
                    doc.close()
                    
                    if text.strip():
                        print(f"✅ PyMuPDF successfully extracted {len(text)} characters")
                        return text.strip()
                    else:
                        print("⚠️ PyMuPDF extracted empty text")
                except ImportError:
                    print("⚠️ PyMuPDF not available")
                except Exception as e:
                    print(f"⚠️ PyMuPDF failed: {e}")
                
                # If all methods fail, return error message
                return "Error: Could not extract text from PDF using any available method. Please paste the content manually or ensure the PDF contains selectable text."
                
            except Exception as e:
                return f"Error extracting text from PDF: {str(e)}\n\nPlease paste the resume content manually."
        
        elif file_extension == 'docx':
            # Extract text from DOCX using python-docx
            try:
                from docx import Document
                doc = Document(uploaded_file)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text.strip() if text.strip() else "No text could be extracted from DOCX. Please paste the content manually."
            except Exception as e:
                return f"Error extracting text from DOCX: {str(e)}\n\nPlease paste the resume content manually."
        
        else:
            # For other file types, try to read as text
            content = uploaded_file.read()
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return content.decode('latin-1', errors='ignore')
    
    except Exception as e:
        return f"Error reading file: {str(e)}\n\nPlease paste the resume content in the text area below."

def clear_database_and_reset():
    """Clear database and reset all session state."""
    try:
        # Clear the database
        st.session_state.resume_processor.clear_database()
        
        # Force clear if regular clear didn't work
        if st.session_state.resume_processor.get_total_resumes() > 0:
            st.session_state.resume_processor.force_clear_database()
        
        # Final aggressive reset if still not cleared
        if st.session_state.resume_processor.get_total_resumes() > 0:
            st.session_state.resume_processor.reset_database()
        
        # Reset job matcher
        st.session_state.job_matcher = None
        
        # Clear any stored rankings
        if 'rankings' in st.session_state:
            del st.session_state.rankings
        
        return True
    except Exception as e:
        st.error(f"Error clearing database: {str(e)}")
        return False

def main():
    st.markdown('<h1 class="main-header">🤖 Agentic AI Resume Matcher (Powered by Gemini AI)</h1>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["📊 Dashboard", "📝 Add Resumes", "🔍 Job Matching", "📋 View Database"]
    )
    
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "📝 Add Resumes":
        show_add_resumes()
    elif page == "🔍 Job Matching":
        show_job_matching()
    elif page == "📋 View Database":
        show_database_view()

def show_dashboard():
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            total_resumes = st.session_state.resume_processor.get_total_resumes()
            st.metric("Total Resumes", total_resumes)
        except:
            st.metric("Total Resumes", 0)
    
    with col2:
        if st.session_state.job_matcher:
            st.metric("System Status", "🟢 Active")
        else:
            st.metric("System Status", "🔴 No Database")
    
    with col3:
        st.metric("AI Model", "Gemini AI")
        st.info("🤖 AI-Powered Resume Processing")
    
    # Initialize automatic email setting
    if 'automatic_emails_enabled' not in st.session_state:
        st.session_state.automatic_emails_enabled = True
    
    st.markdown("---")
    
    # Automatic Email Configuration
    st.subheader("🤖 Automatic Email Configuration")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        automatic_emails = st.checkbox(
            "Enable Automatic Email Sending",
            value=st.session_state.automatic_emails_enabled,
            help="When enabled, emails are automatically sent to qualified candidates (80%+ fit score) immediately after job matching without any user interaction."
        )
        st.session_state.automatic_emails_enabled = automatic_emails
        
        if automatic_emails:
            st.success("✅ Automatic email sending is ENABLED")
            st.info("Emails will be sent automatically to qualified candidates after job matching.")
        else:
            st.warning("⚠️ Automatic email sending is DISABLED")
            st.info("You will need to manually send emails to candidates after job matching.")
    
    with col2:
        email_status = st.session_state.email_service.get_email_configuration_status()
        if email_status["configured"]:
            st.success("📧 Email Service: Configured")
        else:
            st.error("📧 Email Service: Not Configured")
            st.info("Set SENDER_EMAIL and SENDER_PASSWORD in .env file")
    
    st.markdown("---")
    
    # AI Processing Capabilities
    st.markdown("---")
    st.subheader("🤖 AI-Powered Resume Processing")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**📋 Comprehensive Information Extraction**")
        st.write("• Personal Information (Name, Email, Phone, Location)")
        st.write("• Professional Links (LinkedIn, GitHub, Portfolio)")
        st.write("• Technical Skills (Languages, Frameworks, Databases)")
        st.write("• Experience & Education Details")
        st.write("• Certifications & Achievements")
    
    with col2:
        st.info("**🔍 Intelligent Analysis**")
        st.write("• Context-Aware Information Extraction")
        st.write("• Skill Categorization & Normalization")
        st.write("• Experience Level Assessment")
        st.write("• Industry & Work Preference Detection")
        st.write("• Professional Summary Generation")
    
    with col3:
        st.info("**📊 Enhanced Data Quality**")
        st.write("• 25+ Structured Data Fields")
        st.write("• AI-Powered Fallback Extraction")
        st.write("• Consistent Data Formatting")
        st.write("• Comprehensive Skill Mapping")
        st.write("• Professional Profile Building")
    
    st.markdown("---")
    
    # Quick actions
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Database"):
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Database"):
            if st.session_state.resume_processor:
                with st.spinner("Clearing database..."):
                    if clear_database_and_reset():
                        st.success("Database cleared successfully!")
                        st.info("Please refresh the page to see the updated count.")
                        st.rerun()
                    else:
                        st.error("Failed to clear database. Please try again or restart the application.")
    
    with col3:
        if st.button("💥 Force Reset Database"):
            if st.session_state.resume_processor:
                with st.spinner("Force resetting database..."):
                    try:
                        st.session_state.resume_processor.reset_database()
                        st.session_state.job_matcher = None
                        if 'rankings' in st.session_state:
                            del st.session_state.rankings
                        st.success("Database force reset successfully!")
                        st.info("Please refresh the page to see the updated count.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Force reset failed: {str(e)}")
                        st.info("Try restarting the application completely.")
    
    # Debug section
    st.markdown("---")
    st.subheader("🔧 Debug Information")
    
    if st.button("🔍 Check Database Status"):
        try:
            total_resumes = st.session_state.resume_processor.get_total_resumes()
            candidates = st.session_state.resume_processor.get_all_candidates()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Resumes", total_resumes)
            
            with col2:
                st.metric("Candidates Found", len(candidates))
            
            with col3:
                st.metric("Job Matcher Status", "✅ Active" if st.session_state.job_matcher else "❌ Inactive")
            
            if candidates:
                st.write("**📋 Current Candidates:**")
                for candidate in candidates:
                    st.write(f"• {candidate['name']} (ID: {candidate['id']}, Chunks: {candidate['chunks']})")
            else:
                st.warning("No candidates found in database")
                
        except Exception as e:
            st.error(f"Error checking database status: {str(e)}")

def show_add_resumes():
    st.header("📝 Add Resumes")
    
    # Single resume upload
    st.subheader("Upload Single Resume")
    
    uploaded_file = st.file_uploader(
        "Choose a resume file (PDF, TXT, DOCX)",
        type=['pdf', 'txt', 'docx'],
        key="single_resume"
    )
    
    if uploaded_file is not None:
        candidate_name = st.text_input("Candidate Name", key="single_name")
        
        # Extract text from file
        resume_text = extract_text_from_file(uploaded_file)
        
        # Show extracted text for review
        st.subheader("Extracted Resume Content")
        st.text_area("Review and edit the resume content:", resume_text, height=300, key="resume_content")
        
        if candidate_name and st.button("🤖 Process Resume with AI"):
            try:
                # Use the text from the text area (which can be edited)
                final_resume_text = st.session_state.get("resume_content", resume_text)
                
                if final_resume_text.strip():
                    with st.spinner("🤖 AI Agent analyzing resume content..."):
                        result = st.session_state.resume_processor.process_resume(
                            final_resume_text, candidate_name
                        )
                        st.success(result)
                        
                        # Show AI processing summary
                        st.info("✅ Resume processed using AI-powered extraction!")
                        st.info("📋 Comprehensive information extracted including skills, experience, education, and more.")
                    
                    # Reinitialize job matcher
                    st.session_state.job_matcher = JobMatcher()
                else:
                    st.error("Please provide resume content.")
                
            except Exception as e:
                st.error(f"Error processing resume: {str(e)}")
    
    st.markdown("---")
    
    # Manual text input
    st.subheader("Manual Resume Input")
    
    manual_candidate_name = st.text_input("Candidate Name", key="manual_name")
    manual_resume_text = st.text_area(
        "Paste resume content here:",
        height=300,
        placeholder="Paste the resume content here..."
    )
    
    if manual_candidate_name and manual_resume_text.strip() and st.button("🤖 Process Manual Resume with AI"):
        try:
            with st.spinner("🤖 AI Agent analyzing resume content..."):
                result = st.session_state.resume_processor.process_resume(
                    manual_resume_text, manual_candidate_name
                )
                st.success(result)
                
                # Show AI processing summary
                st.info("✅ Resume processed using AI-powered extraction!")
                st.info("📋 Comprehensive information extracted including skills, experience, education, and more.")
            
            # Reinitialize job matcher
            st.session_state.job_matcher = JobMatcher()
            
        except Exception as e:
            st.error(f"Error processing resume: {str(e)}")
    
    st.markdown("---")
    
    # Batch resume upload
    st.subheader("Batch Upload Resumes")
    
    uploaded_files = st.file_uploader(
        "Choose multiple resume files",
        type=['pdf', 'txt', 'docx'],
        accept_multiple_files=True,
        key="batch_resumes"
    )
    
    if uploaded_files:
        st.write(f"Selected {len(uploaded_files)} files")
        
        # Show preview of files to be processed
        st.write("**Files to be processed:**")
        for i, file in enumerate(uploaded_files, 1):
            candidate_name = file.name.replace('.txt', '').replace('.pdf', '').replace('.docx', '')
            st.write(f"{i}. {file.name} → Candidate: {candidate_name}")
        
        if st.button("Process All Resumes"):
            with st.spinner("Processing resumes..."):
                processed_count = 0
                skipped_count = 0
                
                for uploaded_file in uploaded_files:
                    try:
                        resume_text = extract_text_from_file(uploaded_file)
                        candidate_name = uploaded_file.name.replace('.txt', '').replace('.pdf', '').replace('.docx', '')
                        
                        # Skip files that couldn't be processed
                        if "Error reading file" in resume_text or "Error extracting text" in resume_text:
                            error_line = resume_text.split('\n')[0]
                            st.warning(f"Skipped {uploaded_file.name}: {error_line}")
                            skipped_count += 1
                            continue
                        
                        # Process the resume with AI
                        with st.spinner(f"🤖 AI Agent processing {uploaded_file.name}..."):
                            result = st.session_state.resume_processor.process_resume(
                                resume_text, candidate_name
                            )
                            st.success(f"✅ AI-Processed {uploaded_file.name}: {result}")
                            processed_count += 1
                        
                    except Exception as e:
                        st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
                        skipped_count += 1
                
                # Summary
                st.success(f"✅ AI-powered batch processing complete!")
                st.info(f"🤖 AI-Processed: {processed_count} files | Skipped: {skipped_count} files")
                st.info("📋 All processed resumes now contain comprehensive AI-extracted information including skills, experience, education, and more.")
                
                # Reinitialize job matcher
                try:
                    st.session_state.job_matcher = JobMatcher()
                    st.success("✅ Job matcher reinitialized successfully!")
                except Exception as e:
                    st.error(f"❌ Error reinitializing job matcher: {str(e)}")
                
                # Show updated database count
                try:
                    total_resumes = st.session_state.resume_processor.get_total_resumes()
                    st.info(f"📊 Total resumes in database: {total_resumes}")
                except Exception as e:
                    st.error(f"❌ Error getting database count: {str(e)}")

def show_job_matching():
    st.header("🔍 Job Matching")
    
    if not st.session_state.job_matcher:
        st.error("No resume database found. Please add resumes first.")
        return
    
    # Initialize session state for job matching workflow
    if 'job_workflow_state' not in st.session_state:
        st.session_state.job_workflow_state = 'input'
        st.session_state.job_description = ""
        st.session_state.job_validation_result = None
        st.session_state.additional_info = ""
        st.session_state.enhanced_job_data = None
    
    # Job description input and validation workflow
    if st.session_state.job_workflow_state == 'input':
        st.subheader("📝 Step 1: Enter Job Description")
        
        job_description = st.text_area(
            "Enter Job Description",
            value=st.session_state.job_description,
            height=200,
            placeholder="Paste the job description here...",
            key="job_desc_input"
        )
        
        if st.button("🔍 Validate Job Description", type="primary"):
            if job_description.strip():
                st.session_state.job_description = job_description
                
                with st.spinner("Analyzing job description and extracting required information..."):
                    try:
                        # Validate the job description
                        validation_result = st.session_state.job_matcher.validate_job_description(job_description)
                        st.session_state.job_validation_result = validation_result
                        
                        if validation_result["validation"]["is_complete"]:
                            st.session_state.job_workflow_state = 'complete'
                            st.success("✅ Job description is complete! All required information extracted.")
                            st.rerun()
                        else:
                            st.session_state.job_workflow_state = 'missing_data'
                            st.warning(f"⚠️ Job description incomplete. Completeness score: {validation_result['validation']['completeness_score']}%")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error during validation: {str(e)}")
            else:
                st.error("Please enter a job description.")
    
    # Handle missing data collection
    elif st.session_state.job_workflow_state == 'missing_data':
        st.subheader("⚠️ Step 2: Complete Missing Information")
        
        validation_result = st.session_state.job_validation_result
        missing_fields = validation_result["validation"]["missing_fields"]
        
        # Show current completeness
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Completeness Score", f"{validation_result['validation']['completeness_score']}%")
        with col2:
            st.metric("Missing Fields", len(missing_fields))
        
        # Show what's missing
        st.write("**Missing Required Information:**")
        for field_info in missing_fields:
            st.info(f"**{field_info['field'].replace('_', ' ').title()}**: {field_info['description']}")
            st.write(f"*Example: {field_info['example']}*")
        
        # Show extracted data so far
        with st.expander("📋 Currently Extracted Information"):
            extracted_data = validation_result["job_data"]
            for field_name, field_config in st.session_state.job_matcher.job_extractor.required_fields.items():
                if field_config["required"]:
                    value = extracted_data.get(field_name)
                    if value:
                        st.write(f"✅ **{field_name.replace('_', ' ').title()}**: {value}")
                    else:
                        st.write(f"❌ **{field_name.replace('_', ' ').title()}**: Missing")
        
        # Input for additional information
        st.write("**Please provide the missing information:**")
        additional_info = st.text_area(
            "Additional Information",
            value=st.session_state.additional_info,
            height=150,
            placeholder="Provide the missing information here. Be specific and detailed...",
            key="additional_info_input"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Re-validate with Additional Info"):
                if additional_info.strip():
                    st.session_state.additional_info = additional_info
                    
                    with st.spinner("Enhancing job data with additional information..."):
                        try:
                            enhanced_result = st.session_state.job_matcher.enhance_job_description(
                                st.session_state.job_description, 
                                additional_info
                            )
                            st.session_state.enhanced_job_data = enhanced_result
                            
                            if enhanced_result["validation"]["is_complete"]:
                                st.session_state.job_workflow_state = 'complete'
                                st.success("✅ Job description is now complete!")
                                st.rerun()
                            else:
                                st.session_state.job_validation_result = enhanced_result
                                st.warning(f"⚠️ Still incomplete. New completeness score: {enhanced_result['validation']['completeness_score']}%")
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Error enhancing job data: {str(e)}")
                else:
                    st.error("Please provide additional information.")
        
        with col2:
            if st.button("🔄 Start Over"):
                st.session_state.job_workflow_state = 'input'
                st.session_state.job_description = ""
                st.session_state.job_validation_result = None
                st.session_state.additional_info = ""
                st.session_state.enhanced_job_data = None
                st.rerun()
    
    # Job description is complete, proceed with ranking
    elif st.session_state.job_workflow_state == 'complete':
        st.subheader("✅ Step 3: Job Description Complete - Ready for Ranking")
        
        # Show final job data
        if st.session_state.enhanced_job_data:
            final_data = st.session_state.enhanced_job_data["job_data"]
        else:
            final_data = st.session_state.job_validation_result["job_data"]
        
        # Ensure all list fields are properly initialized
        if not isinstance(final_data.get('required_skills'), list):
            final_data['required_skills'] = []
        if not isinstance(final_data.get('preferred_skills'), list):
            final_data['preferred_skills'] = []
        if not isinstance(final_data.get('key_responsibilities'), list):
            final_data['key_responsibilities'] = []
        
        with st.expander("📋 Final Job Requirements"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Basic Information:**")
                st.write(f"• **Job Title**: {final_data.get('job_title', 'N/A')}")
                st.write(f"• **Company**: Jman Group")
                st.write(f"• **Industry**: {final_data.get('industry', 'N/A')}")
                st.write(f"• **Experience Level**: {final_data.get('experience_level', 'N/A')}")
                st.write(f"• **Location**: {final_data.get('location', 'N/A')}")
            
            with col2:
                st.write("**Skills & Requirements:**")
                required_skills = final_data.get('required_skills', []) or []
                preferred_skills = final_data.get('preferred_skills', []) or []
                st.write(f"• **Required Skills**: {', '.join(required_skills) if required_skills else 'N/A'}")
                st.write(f"• **Preferred Skills**: {', '.join(preferred_skills) if preferred_skills else 'N/A'}")
                st.write(f"• **Education**: {final_data.get('education_requirements', 'N/A')}")
        
        st.write("**Key Responsibilities:**")
        key_responsibilities = final_data.get('key_responsibilities', []) or []
        if key_responsibilities:
            for i, resp in enumerate(key_responsibilities, 1):
                st.write(f"{i}. {resp}")
        else:
            st.write("N/A")
        
        # Automatic Email Status
        st.markdown("---")
        st.subheader("🤖 Automatic Email Status")
        
        if st.session_state.get('automatic_emails_enabled', True):
            st.success("✅ **Automatic Email Sending is ENABLED**")
            st.info("When you click 'Find Best Matches', emails will be automatically sent to qualified candidates (80%+ fit score) without any user interaction.")
        else:
            st.warning("⚠️ **Automatic Email Sending is DISABLED**")
            st.info("You will need to manually send emails to candidates after job matching. Enable automatic emails in the Dashboard.")
        
        # Ranking options
        st.markdown("---")
        st.subheader("🎯 Step 4: Configure Ranking")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            top_k = st.slider("Number of top candidates", 5, 20, 10, key="ranking_top_k")
        
        with col2:
            if st.button("🔍 Find Best Matches", type="primary"):
                with st.spinner("Analyzing job requirements and ranking candidates with Gemini AI..."):
                    try:
                        # Use the complete job description for ranking
                        if st.session_state.enhanced_job_data:
                            # Combine original description with additional info for better context
                            full_description = f"{st.session_state.job_description}\n\nAdditional Information: {st.session_state.additional_info}"
                        else:
                            full_description = st.session_state.job_description
                        
                        rankings = st.session_state.job_matcher.rank_resumes(full_description, top_k)
                        st.session_state.rankings = rankings
                        st.session_state.job_workflow_state = 'ranking_results'
                        
                        # AUTOMATIC EMAIL SENDING - No user interaction required
                        st.success(f"Found {len(rankings)} top candidates!")
                        
                        # Automatically send emails to candidates with 80%+ fit score (if enabled)
                        selected_candidates = [c for c in rankings if c['fit_score'] >= 80]
                        if selected_candidates:
                            if st.session_state.get('automatic_emails_enabled', True):
                                st.info("🚀 Automatically sending selection emails to qualified candidates...")
                                
                                with st.spinner("Sending selection emails automatically..."):
                                    try:
                                        # Send emails automatically without user interaction using the new method
                                        email_result = st.session_state.email_service.send_automatic_selection_emails(
                                            selected_candidates, final_data
                                        )
                                        
                                        # Store results for display
                                        st.session_state.email_results = email_result
                                        st.session_state.show_email_results = True
                                        
                                        if email_result["success"]:
                                            st.success(f"✅ All {email_result['emails_sent']} selection emails sent automatically!")
                                        else:
                                            st.warning(f"⚠️ {email_result['emails_sent']} emails sent, {email_result['emails_failed']} failed.")
                                        
                                    except Exception as e:
                                        st.error(f"❌ Error sending automatic emails: {str(e)}")
                                        st.info("You can still send emails manually using the buttons below.")
                            else:
                                st.info("ℹ️ Automatic email sending is disabled. You can send emails manually using the buttons below.")
                        else:
                            st.info("ℹ️ No candidates found with 80%+ fit score eligible for automatic email sending.")
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error during matching: {str(e)}")
        
        with col3:
            if st.button("🔄 Start New Job"):
                st.session_state.job_workflow_state = 'input'
                st.session_state.job_description = ""
                st.session_state.job_validation_result = None
                st.session_state.additional_info = ""
                st.session_state.enhanced_job_data = None
                if 'rankings' in st.session_state:
                    del st.session_state.rankings
                st.rerun()
    
    # Display ranking results
    elif st.session_state.job_workflow_state == 'ranking_results':
        st.subheader("🏆 Ranking Results")
        
        if hasattr(st.session_state, 'rankings') and st.session_state.rankings:
            # Show job summary
            if st.session_state.enhanced_job_data:
                final_data = st.session_state.enhanced_job_data["job_data"]
            else:
                final_data = st.session_state.job_validation_result["job_data"]
            
            # Ensure all list fields are properly initialized
            if not isinstance(final_data.get('required_skills'), list):
                final_data['required_skills'] = []
            if not isinstance(final_data.get('preferred_skills'), list):
                final_data['preferred_skills'] = []
            if not isinstance(final_data.get('key_responsibilities'), list):
                final_data['key_responsibilities'] = []
            
            st.info(f"**Job**: {final_data.get('job_title', 'N/A')} at Jman Group")
            
            # Automatic Email Results Summary (if available)
            if hasattr(st.session_state, 'email_results') and st.session_state.email_results:
                st.markdown("---")
                st.subheader("🤖 Automatic Email Results")
                
                email_results = st.session_state.email_results
                
                # Show automatic sending status
                if email_results.get('automatic_sending'):
                    st.success("✅ **Automatic Email Sending Completed**")
                    
                    # Show summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Candidates", email_results['total_candidates'])
                    with col2:
                        st.metric("Emails Sent", email_results['emails_sent'], delta=f"+{email_results['emails_sent']}")
                    with col3:
                        st.metric("Emails Failed", email_results['emails_failed'], delta=f"-{email_results['emails_failed']}")
                    with col4:
                        success_rate = (email_results['emails_sent'] / email_results['total_candidates'] * 100) if email_results['total_candidates'] > 0 else 0
                        st.metric("Success Rate", f"{success_rate:.1f}%")
                    
                    # Show enhanced summary if available
                    if email_results.get('enhanced_summary'):
                        with st.expander("📊 Automatic Email Summary", expanded=True):
                            st.markdown(email_results['enhanced_summary'])
                    
                    # Show summary message
                    if email_results['summary']:
                        if email_results['success']:
                            st.success(email_results['summary'])
                        elif email_results['emails_sent'] > 0:
                            st.warning(email_results['summary'])
                        else:
                            st.error(email_results['summary'])
                else:
                    st.info("📧 Manual email sending results available below.")
            
            # Candidate Selection and Email Section
            st.markdown("---")
            st.subheader("📧 Candidate Selection & Email Notifications")
            
            # Email configuration status
            email_status = st.session_state.email_service.get_email_configuration_status()
            if not email_status["configured"]:
                st.warning("⚠️ Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in your .env file to send selection emails.")
                st.info("**Required Environment Variables:**")
                st.code("""
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
COMPANY_NAME=Your Company Name
HR_CONTACT=hr@company.com
                """)
            else:
                st.success("✅ Email service configured and ready to send selection emails.")
            
            # Filter candidates with 80%+ fit score
            selected_candidates = [c for c in st.session_state.rankings if c['fit_score'] >= 80]
            
            if selected_candidates:
                st.success(f"🎯 Found {len(selected_candidates)} candidates with 80%+ fit score eligible for selection emails!")
                
                # Show selected candidates
                st.write("**Selected Candidates (80%+ Fit Score):**")
                for candidate in selected_candidates:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**{candidate['candidate_name']}** - Score: {candidate['fit_score']}%")
                        if candidate.get('email'):
                            st.write(f"📧 {candidate['email']}")
                        else:
                            st.write("❌ No email address found")
                    
                    with col2:
                        if candidate.get('email'):
                            if st.button(f"📧 Send Email", key=f"send_email_{candidate['candidate_id']}"):
                                with st.spinner(f"Sending email to {candidate['candidate_name']}..."):
                                    email_result = st.session_state.email_service.send_job_selection_email(
                                        candidate['email'], candidate, final_data
                                    )
                                    
                                    if email_result["success"]:
                                        st.success(f"✅ Email sent to {candidate['candidate_name']}!")
                                    else:
                                        st.error(f"❌ Failed to send email: {email_result.get('error', 'Unknown error')}")
                        else:
                            st.warning("No email")
                    
                    with col3:
                        if candidate.get('email'):
                            if st.button(f"👁️ Preview", key=f"preview_email_{candidate['candidate_id']}"):
                                email_preview = st.session_state.email_service.generate_email_template_preview(
                                    candidate, final_data
                                )
                                st.text_area("Email Preview", email_preview, height=300, key=f"preview_{candidate['candidate_id']}")
                
                # Bulk email actions
                st.markdown("---")
                st.subheader("📬 Bulk Email Actions")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button("📧 Send All Selection Emails", type="primary"):
                        with st.spinner("Sending selection emails to all eligible candidates..."):
                            bulk_result = st.session_state.email_service.send_bulk_selection_emails(
                                selected_candidates, final_data
                            )
                            
                            if bulk_result["success"]:
                                st.success(f"✅ Successfully sent {bulk_result['emails_sent']} emails!")
                            else:
                                st.warning(f"⚠️ Sent {bulk_result['emails_sent']} emails, {bulk_result['emails_failed']} failed.")
                                
                                if bulk_result['failed_sends']:
                                    st.write("**Failed Sends:**")
                                    for failed in bulk_result['failed_sends']:
                                        st.error(f"• {failed['candidate_name']}: {failed.get('error', 'Unknown error')}")
                
                with col2:
                    if st.button("🚀 Send Emails Immediately", type="primary"):
                        with st.spinner("Sending emails immediately with detailed feedback..."):
                            immediate_result = st.session_state.email_service.send_immediate_selection_emails(
                                selected_candidates, final_data
                            )
                            
                            # Store results in session state for display
                            st.session_state.email_results = immediate_result
                            
                            if immediate_result["success"]:
                                st.success(f"✅ All {immediate_result['emails_sent']} emails sent successfully!")
                            else:
                                st.warning(f"⚠️ {immediate_result['emails_sent']} sent, {immediate_result['emails_failed']} failed.")
                            
                            # Show detailed results
                            st.session_state.show_email_results = True
                            st.rerun()
                
                with col3:
                    if st.button("📊 Email Summary"):
                        st.write("**Email Summary:**")
                        st.metric("Total Selected", len(selected_candidates))
                        st.metric("With Email Addresses", len([c for c in selected_candidates if c.get('email')]))
                        st.metric("Without Email Addresses", len([c for c in selected_candidates if not c.get('email')]))
                
                with col4:
                    if st.button("📋 Export Selected Candidates"):
                        # Create export data
                        export_data = []
                        for candidate in selected_candidates:
                            # Ensure all fields are safely extracted
                            strengths = candidate.get('strengths', []) or []
                            weaknesses = candidate.get('weaknesses', []) or []
                            missing_skills = candidate.get('missing_skills', []) or []
                            
                            export_data.append({
                                "Rank": candidate['rank'],
                                "Name": candidate['candidate_name'],
                                "Fit Score": candidate['fit_score'],
                                "Email": candidate.get('email', 'N/A'),
                                "Phone": candidate.get('phone', 'N/A'),
                                "LinkedIn": candidate.get('linkedin', 'N/A'),
                                "Recommendation": candidate['recommendation'],
                                "Strengths": '; '.join(strengths) if strengths else 'N/A',
                                "Weaknesses": '; '.join(weaknesses) if weaknesses else 'N/A',
                                "Missing Skills": '; '.join(missing_skills) if missing_skills else 'N/A'
                            })
                        
                        # Convert to DataFrame and download
                        df = pd.DataFrame(export_data)
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"selected_candidates_{final_data.get('job_title', 'job')}.csv",
                            mime="text/csv"
                        )
                
                # Display detailed email results if available
                if hasattr(st.session_state, 'show_email_results') and st.session_state.show_email_results:
                    if hasattr(st.session_state, 'email_results') and st.session_state.email_results:
                        st.markdown("---")
                        st.subheader("📧 Detailed Email Results")
                        
                        email_results = st.session_state.email_results
                        
                        # Show enhanced summary if available
                        if email_results.get('enhanced_summary'):
                            with st.expander("🎯 Enhanced Email Summary", expanded=True):
                                st.markdown(email_results['enhanced_summary'])
                        
                        # Show summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Candidates", email_results['total_candidates'])
                        with col2:
                            st.metric("Emails Sent", email_results['emails_sent'], delta=f"+{email_results['emails_sent']}")
                        with col3:
                            st.metric("Emails Failed", email_results['emails_failed'], delta=f"-{email_results['emails_failed']}")
                        with col4:
                            success_rate = (email_results['emails_sent'] / email_results['total_candidates'] * 100) if email_results['total_candidates'] > 0 else 0
                            st.metric("Success Rate", f"{success_rate:.1f}%")
                        
                        # Show summary
                        if email_results['summary']:
                            if email_results['success']:
                                st.success(email_results['summary'])
                            elif email_results['emails_sent'] > 0:
                                st.warning(email_results['summary'])
                            else:
                                st.error(email_results['summary'])
                        
                        # Show successful sends
                        if email_results['successful_sends']:
                            with st.expander(f"✅ Successful Sends ({len(email_results['successful_sends'])})"):
                                for success in email_results['successful_sends']:
                                    rank = success.get('rank', 'N/A')
                                    email = success.get('candidate_email', success.get('email', 'N/A'))
                                    st.success(f"**{success['candidate_name']}** (Rank #{rank}) - {email} - Sent at {success['timestamp']}")
                        
                        # Show failed sends with reasons
                        if email_results['failed_sends']:
                            with st.expander(f"❌ Failed Sends ({len(email_results['failed_sends'])})"):
                                # Group failures by reason for better analysis
                                failure_reasons = {}
                                for failed in email_results['failed_sends']:
                                    reason = failed.get('error', 'Unknown error')
                                    if reason not in failure_reasons:
                                        failure_reasons[reason] = []
                                    failure_reasons[reason].append(failed)
                                
                                for reason, failures in failure_reasons.items():
                                    st.error(f"**Reason: {reason}** ({len(failures)} occurrences)")
                                    for failed in failures:
                                        rank = failed.get('rank', 'N/A')
                                        st.write(f"• {failed['candidate_name']} (Rank #{rank}) - {failed['email']} - Failed at {failed['timestamp']}")
                                    st.markdown("---")
                        
                        # Show detailed report
                        if hasattr(email_results, 'detailed_report'):
                            with st.expander("📋 Complete Email Report"):
                                st.text(email_results['detailed_report'])
                        
                        # Action buttons for email results
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("🔄 Send Failed Emails Again"):
                                # Filter only failed candidates
                                failed_candidates = [c for c in selected_candidates if c.get('email') in [f['email'] for f in email_results['failed_sends']]]
                                if failed_candidates:
                                    with st.spinner("Retrying failed emails..."):
                                        retry_result = st.session_state.email_service.send_bulk_selection_emails(
                                            failed_candidates, final_data
                                        )
                                        st.success(f"Retry completed: {retry_result['emails_sent']} sent, {retry_result['emails_failed']} failed")
                                        st.rerun()
                                else:
                                    st.info("No failed emails to retry")
                        
                        with col2:
                            if st.button("📊 Export Email Results"):
                                # Create export data for email results
                                export_data = []
                                for success in email_results.get('successful_sends', []):
                                    export_data.append({
                                        "Status": "Success",
                                        "Candidate": success['candidate_name'],
                                        "Rank": success.get('rank', 'N/A'),
                                        "Email": success.get('candidate_email', success.get('email', 'N/A')),
                                        "Fit Score": success['fit_score'],
                                        "Sent At": success['timestamp']
                                    })
                                
                                for failed in email_results.get('failed_sends', []):
                                    export_data.append({
                                        "Status": "Failed",
                                        "Candidate": failed['candidate_name'],
                                        "Rank": failed.get('rank', 'N/A'),
                                        "Email": failed['email'],
                                        "Fit Score": failed['fit_score'],
                                        "Error": failed.get('error', 'Unknown error'),
                                        "Failed At": failed['timestamp']
                                    })
                                
                                # Convert to DataFrame and download
                                df = pd.DataFrame(export_data)
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Email Results CSV",
                                    data=csv,
                                    file_name=f"email_results_{final_data.get('job_title', 'job')}.csv",
                                    mime="text/csv"
                                )
                        
                        with col3:
                            if st.button("📧 Close Email Results"):
                                st.session_state.show_email_results = False
                                if 'email_results' in st.session_state:
                                    del st.session_state.email_results
                                st.rerun()
            else:
                st.info("ℹ️ No candidates found with 80%+ fit score. Consider adjusting the job requirements or reviewing the candidate pool.")
            
            # Display all rankings
            st.markdown("---")
            st.subheader("📊 All Candidate Rankings")
            
            for i, candidate in enumerate(st.session_state.rankings):
                with st.expander(f"#{candidate['rank']} - {candidate['candidate_name']} (Score: {candidate['fit_score']}/100)"):
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        st.metric("Fit Score", f"{candidate['fit_score']}/100")
                        st.metric("Recommendation", candidate['recommendation'].replace('_', ' ').title())
                        
                        # Show contact info
                        if candidate.get('email'):
                            st.write(f"📧 **Email:** {candidate['email']}")
                        else:
                            st.write("❌ **Email:** Not available")
                        if candidate.get('phone'):
                            st.write(f"📱 **Phone:** {candidate['phone']}")
                        if candidate.get('linkedin'):
                            st.write(f"🔗 **LinkedIn:** {candidate['linkedin']}")
                    
                    with col2:
                        # Show rank reason prominently
                        if candidate.get('rank_reason'):
                            st.write("**🎯 Rank Reason:**")
                            st.success(candidate['rank_reason'])
                        
                        # Show key matches
                        if candidate.get('key_matches'):
                            st.write("**🔗 Key Matches:**")
                            for match in candidate['key_matches']:
                                st.markdown(f'<span class="strength-tag">{match}</span>', unsafe_allow_html=True)
                        
                        if candidate['strengths']:
                            st.write("**✅ Strengths:**")
                            for strength in candidate['strengths']:
                                st.markdown(f'<span class="strength-tag">{strength}</span>', unsafe_allow_html=True)
                        
                        if candidate['weaknesses']:
                            st.write("**⚠️ Areas for Improvement:**")
                            for weakness in candidate['weaknesses']:
                                st.markdown(f'<span class="weakness-tag">{weakness}</span>', unsafe_allow_html=True)
                        
                        if candidate['missing_skills']:
                            st.write("**❌ Missing Skills:**")
                            for skill in candidate['missing_skills']:
                                st.markdown(f'<span class="weakness-tag">{skill}</span>', unsafe_allow_html=True)
                        
                        # Show improvement areas if available
                        if candidate.get('improvement_areas'):
                            st.write("**📈 Improvement Areas:**")
                            for area in candidate['improvement_areas']:
                                st.markdown(f'<span class="weakness-tag">{area}</span>', unsafe_allow_html=True)
                    
                    with col3:
                        # Show detailed assessment metrics
                        st.write("**📊 Assessment Metrics:**")
                        
                        # Technical expertise
                        tech_level = candidate.get('technical_expertise', 'medium')
                        if tech_level == 'high':
                            st.success(f"🔧 Technical: {tech_level.title()}")
                        elif tech_level == 'medium':
                            st.warning(f"🔧 Technical: {tech_level.title()}")
                        else:
                            st.error(f"🔧 Technical: {tech_level.title()}")
                        
                        # Experience relevance
                        exp_level = candidate.get('experience_relevance', 'medium')
                        if exp_level == 'high':
                            st.success(f"💼 Experience: {exp_level.title()}")
                        elif exp_level == 'medium':
                            st.warning(f"💼 Experience: {exp_level.title()}")
                        else:
                            st.error(f"💼 Experience: {exp_level.title()}")
                        
                        # Skill alignment
                        skill_level = candidate.get('skill_alignment', 'medium')
                        if skill_level == 'high':
                            st.success(f"🎯 Skills: {skill_level.title()}")
                        elif skill_level == 'medium':
                            st.warning(f"🎯 Skills: {skill_level.title()}")
                        else:
                            st.error(f"🎯 Skills: {skill_level.title()}")
                        
                        # Growth potential
                        growth_level = candidate.get('growth_potential', 'medium')
                        if growth_level == 'high':
                            st.success(f"📈 Growth: {growth_level.title()}")
                        elif growth_level == 'medium':
                            st.warning(f"📈 Growth: {growth_level.title()}")
                        else:
                            st.error(f"📈 Growth: {growth_level.title()}")
                    
                    st.write("**💡 Detailed Reasoning:**")
                    st.write(candidate['reasoning'])
                    
                    st.write("**📄 Resume Preview:**")
                    st.text(candidate['content_preview'])
            
            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Rank Different Number"):
                    st.session_state.job_workflow_state = 'complete'
                    st.rerun()
            
            with col2:
                if st.button("🔄 Start New Job"):
                    st.session_state.job_workflow_state = 'input'
                    st.session_state.job_description = ""
                    st.session_state.job_validation_result = None
                    st.session_state.additional_info = ""
                    st.session_state.enhanced_job_data = None
                    if 'rankings' in st.session_state:
                        del st.session_state.rankings
                    st.rerun()

def show_database_view():
    st.header("📋 Database Overview")
    
    if not st.session_state.job_matcher:
        st.error("No resume database found.")
        return
    
    try:
        total_resumes = st.session_state.resume_processor.get_total_resumes()
        st.metric("Total Resumes in Database", total_resumes)
        
        if total_resumes == 0:
            st.info("No resumes found in the database. Add some resumes first!")
            return
        
        # Get all candidates using the new method
        candidates = st.session_state.resume_processor.get_all_candidates()
        
        # Debug information
        st.info(f"Debug: Found {len(candidates)} candidates in database")
        
        if not candidates:
            st.info("No candidates found in the database.")
            return
        
        # Display each candidate's resume
        st.subheader("📄 Stored Resumes")
        
        for i, candidate_data in enumerate(candidates, 1):
            with st.expander(f"#{i} - {candidate_data['name']} ({candidate_data['chunks']} chunks)"):
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    st.metric("Candidate ID", candidate_data['id'])
                    st.metric("Content Chunks", candidate_data['chunks'])
                
                with col2:
                    # Display AI-extracted information prominently
                    st.write("**🤖 AI-Extracted Information:**")
                    
                    # Contact Information
                    col_contact1, col_contact2 = st.columns(2)
                    with col_contact1:
                        if candidate_data.get('email'):
                            st.success(f"📧 **Email:** {candidate_data['email']}")
                        if candidate_data.get('phone'):
                            st.info(f"📱 **Phone:** {candidate_data['phone']}")
                        if candidate_data.get('location'):
                            st.info(f"📍 **Location:** {candidate_data['location']}")
                    
                    with col_contact2:
                        if candidate_data.get('linkedin'):
                            st.success(f"🔗 **LinkedIn:** {candidate_data['linkedin']}")
                        if candidate_data.get('github'):
                            st.success(f"💻 **GitHub:** {candidate_data['github']}")
                        if candidate_data.get('portfolio'):
                            st.success(f"🌐 **Portfolio:** {candidate_data['portfolio']}")
                    
                    # Technical Skills
                    st.write("**💻 Technical Skills:**")
                    col_skills1, col_skills2, col_skills3 = st.columns(3)
                    
                    with col_skills1:
                        if candidate_data.get('programming_languages'):
                            st.write(f"**Programming Languages:** {candidate_data['programming_languages']}")
                        if candidate_data.get('frameworks'):
                            st.write(f"**Frameworks:** {candidate_data['frameworks']}")
                    
                    with col_skills2:
                        if candidate_data.get('databases'):
                            st.write(f"**Databases:** {candidate_data['databases']}")
                        if candidate_data.get('cloud_platforms'):
                            st.write(f"**Cloud Platforms:** {candidate_data['cloud_platforms']}")
                    
                    with col_skills3:
                        if candidate_data.get('devops_tools'):
                            st.write(f"**DevOps Tools:** {candidate_data['devops_tools']}")
                        if candidate_data.get('other_technologies'):
                            st.write(f"**Other Technologies:** {candidate_data['other_technologies']}")
                    
                    # Experience & Education
                    st.write("**🎓 Experience & Education:**")
                    col_exp1, col_exp2 = st.columns(2)
                    
                    with col_exp1:
                        if candidate_data.get('total_experience_years'):
                            st.metric("Experience", f"{candidate_data['total_experience_years']} years")
                        if candidate_data.get('education_level'):
                            st.write(f"**Education:** {candidate_data['education_level']}")
                    
                    with col_exp2:
                        if candidate_data.get('degree_field'):
                            st.write(f"**Field of Study:** {candidate_data['degree_field']}")
                        if candidate_data.get('spoken_languages'):
                            st.write(f"**Languages:** {candidate_data['spoken_languages']}")
                    
                    # Additional Information
                    if candidate_data.get('certifications') or candidate_data.get('key_achievements') or candidate_data.get('work_preferences') or candidate_data.get('industries'):
                        st.write("**📋 Additional Information:**")
                        
                        if candidate_data.get('certifications'):
                            st.write(f"**Certifications:** {candidate_data['certifications']}")
                        if candidate_data.get('key_achievements'):
                            st.write(f"**Key Achievements:** {candidate_data['key_achievements']}")
                        if candidate_data.get('work_preferences'):
                            st.write(f"**Work Preferences:** {candidate_data['work_preferences']}")
                        if candidate_data.get('industries'):
                            st.write(f"**Industries:** {candidate_data['industries']}")
                    
                    # Professional Summary
                    if candidate_data.get('professional_summary'):
                        st.write("**📝 Professional Summary:**")
                        st.info(candidate_data['professional_summary'])
                    
                    st.markdown("---")
                    
                    # Full Resume Content
                    st.write("**📄 Full Resume Content:**")
                    full_content = " ".join(candidate_data['content'])
                    
                    # Show first 1000 characters with option to expand
                    if len(full_content) > 1000:
                        st.text_area(
                            f"Resume Content (showing first 1000 chars of {len(full_content)} total)",
                            full_content[:1000] + "...",
                            height=200,
                            key=f"resume_preview_{candidate_data['id']}"
                        )
                        
                        # Show full content in a separate section
                        st.write("**📄 Complete Resume Content:**")
                        st.text_area(
                            "Complete Resume Content",
                            full_content,
                            height=400,
                            key=f"resume_full_{candidate_data['id']}"
                        )
                    else:
                        st.text_area(
                            "Resume Content",
                            full_content,
                            height=200,
                            key=f"resume_content_{candidate_data['id']}"
                        )
        
        # Database statistics
        st.markdown("---")
        st.subheader("📊 Database Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Candidates", len(candidates))
        
        with col2:
            total_chunks = sum(candidate_data['chunks'] for candidate_data in candidates)
            st.metric("Total Content Chunks", total_chunks)
        
        with col3:
            avg_chunks = total_chunks / len(candidates) if candidates else 0
            st.metric("Avg Chunks per Resume", f"{avg_chunks:.1f}")
        
        with col4:
            # Count candidates with AI-extracted information
            candidates_with_ai_data = sum(1 for c in candidates if c.get('programming_languages') or c.get('frameworks') or c.get('databases'))
            st.metric("AI-Enhanced Profiles", candidates_with_ai_data)
        
        # AI Extraction Statistics
        st.markdown("---")
        st.subheader("🤖 AI Extraction Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Skills extraction stats
            total_skills = 0
            for candidate in candidates:
                if candidate.get('programming_languages'):
                    total_skills += len(candidate['programming_languages'].split('; ')) if candidate['programming_languages'] else 0
                if candidate.get('frameworks'):
                    total_skills += len(candidate['frameworks'].split('; ')) if candidate['frameworks'] else 0
                if candidate.get('databases'):
                    total_skills += len(candidate['databases'].split('; ')) if candidate['databases'] else 0
            st.metric("Total Skills Extracted", total_skills)
        
        with col2:
            # Contact info extraction stats
            candidates_with_email = sum(1 for c in candidates if c.get('email'))
            candidates_with_phone = sum(1 for c in candidates if c.get('phone'))
            candidates_with_linkedin = sum(1 for c in candidates if c.get('linkedin'))
            st.metric("Contact Info Extracted", f"{candidates_with_email}/{len(candidates)}")
        
        with col3:
            # Experience extraction stats
            candidates_with_exp = sum(1 for c in candidates if c.get('total_experience_years') and c.get('total_experience_years') > 0)
            st.metric("Experience Extracted", f"{candidates_with_exp}/{len(candidates)}")
        
        with col4:
            # Education extraction stats
            candidates_with_edu = sum(1 for c in candidates if c.get('education_level') and c.get('education_level') != "Not specified")
            st.metric("Education Extracted", f"{candidates_with_edu}/{len(candidates)}")
        
        # Show candidate list with AI-extracted information
        st.write("**📋 Candidate List with AI-Extracted Information:**")
        
        for candidate_data in candidates:
            with st.expander(f"👤 {candidate_data['name']} (ID: {candidate_data['id']})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Contact Information:**")
                    if candidate_data.get('email'):
                        st.write(f"📧 {candidate_data['email']}")
                    if candidate_data.get('phone'):
                        st.write(f"📱 {candidate_data['phone']}")
                    if candidate_data.get('location'):
                        st.write(f"📍 {candidate_data['location']}")
                    
                    st.write("**Professional Links:**")
                    if candidate_data.get('linkedin'):
                        st.write(f"🔗 {candidate_data['linkedin']}")
                    if candidate_data.get('github'):
                        st.write(f"💻 {candidate_data['github']}")
                    if candidate_data.get('portfolio'):
                        st.write(f"🌐 {candidate_data['portfolio']}")
                
                with col2:
                    st.write("**Technical Skills:**")
                    if candidate_data.get('programming_languages'):
                        st.write(f"**Languages:** {candidate_data['programming_languages']}")
                    if candidate_data.get('frameworks'):
                        st.write(f"**Frameworks:** {candidate_data['frameworks']}")
                    if candidate_data.get('databases'):
                        st.write(f"**Databases:** {candidate_data['databases']}")
                    
                    st.write("**Experience & Education:**")
                    if candidate_data.get('total_experience_years'):
                        st.write(f"**Experience:** {candidate_data['total_experience_years']} years")
                    if candidate_data.get('education_level'):
                        st.write(f"**Education:** {candidate_data['education_level']}")
                    if candidate_data.get('degree_field'):
                        st.write(f"**Field:** {candidate_data['degree_field']}")
        
        # Add a refresh button
        if st.button("🔄 Refresh Database View"):
            st.rerun()
        
    except Exception as e:
        st.error(f"Error accessing database: {str(e)}")
        st.info("Try refreshing the page or restarting the application.")
        
        # Add debugging information
        st.write("**Debug Information:**")
        st.write(f"Total resumes reported: {total_resumes}")
        st.write(f"Candidates found: {len(candidates) if 'candidates' in locals() else 'N/A'}")
        st.write(f"Job matcher exists: {st.session_state.job_matcher is not None}")
        st.write(f"Resume processor exists: {st.session_state.resume_processor is not None}")

if __name__ == "__main__":
    main() 