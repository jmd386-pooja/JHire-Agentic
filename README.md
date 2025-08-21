# 🤖 Agentic AI Resume Matcher (Powered by Gemini AI)

An intelligent resume matching system powered by LangChain and Google's Gemini AI that uses vector databases to rank candidates based on job descriptions. The system provides detailed analysis of candidate fit, strengths, weaknesses, and recommendations.

## ✨ Features

### 🎯 Core Functionality
- **Vector Database Storage**: Store and index resumes using ChromaDB
- **Intelligent Job Analysis**: Extract requirements and skills from job descriptions using Gemini AI
- **Smart Resume Ranking**: Rank candidates based on similarity and detailed fit analysis
- **Comprehensive Analysis**: Provide strengths, weaknesses, missing skills, and reasoning

### 🖥️ Web Interface
- **Modern UI**: Beautiful Streamlit-based web application
- **Dashboard**: Overview of system status and database statistics
- **Resume Upload**: Single and batch resume upload capabilities
- **Job Matching**: Interactive job description input and candidate ranking
- **Detailed Results**: Expandable candidate cards with comprehensive analysis

### 🔧 Technical Features
- **LangChain Integration**: Leverages LangChain for LLM interactions and document processing
- **Gemini AI Embeddings**: High-quality semantic embeddings for similarity matching
- **ChromaDB**: Persistent vector database for resume storage
- **Modular Architecture**: Clean separation of concerns with dedicated modules

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google AI API key (Gemini AI)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd agentic_ai
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   # Copy the example environment file
   cp env_example.txt .env
   
   # Edit .env and add your Google AI API key
   GOOGLE_API_KEY=your_google_api_key_here
   CHROMA_DB_PATH=./chroma_db
   ```

4. **Populate with sample data (optional)**
   ```bash
   python sample_data.py
   ```

5. **Run the application (Choose one method)**

   **Method 1: Using the startup script (Recommended)**
   ```bash
   python start_app.py
   ```
   
   **Method 2: Direct Streamlit command**
   ```bash
   streamlit run app.py
   ```
   
   **Note**: The startup script automatically suppresses ChromaDB telemetry warnings.

6. **Open your browser**
   Navigate to `http://localhost:8501`

## 📁 Project Structure

```
agentic_ai/
├── app.py                 # Main Streamlit application
├── resume_processor.py    # Resume processing and vector database management
├── job_matcher.py        # Job analysis and candidate ranking logic
├── sample_data.py        # Sample resume data generator
├── requirements.txt      # Python dependencies
├── env_example.txt      # Environment variables template
├── README.md            # This file
└── chroma_db/          # Vector database storage (created automatically)
```

## 🔧 Usage

### 1. Adding Resumes

#### Single Resume Upload
1. Navigate to "📝 Add Resumes" in the sidebar
2. Upload a resume file (PDF, TXT, DOCX)
3. Enter the candidate's name
4. Click "Process Resume"

#### Batch Upload
1. Select multiple resume files
2. Click "Process All Resumes"
3. Files will be processed automatically using filenames as candidate names

### 2. Job Matching

1. Navigate to "🔍 Job Matching" in the sidebar
2. Paste a job description in the text area
3. Adjust the number of top candidates (5-20)
4. Click "🔍 Find Best Matches"
5. Review the ranked results with detailed analysis

### 3. Sample Job Descriptions

Here are some example job descriptions to test the system:

#### Software Engineer
```
We are looking for a Senior Software Engineer to join our team. The ideal candidate will have:
- 5+ years of experience in Python, JavaScript, and web development
- Experience with React, Django, and cloud technologies (AWS)
- Knowledge of microservices architecture and CI/CD pipelines
- Strong problem-solving skills and ability to mentor junior developers
- Experience with PostgreSQL, Docker, and Git
```

#### Data Scientist
```
We're hiring a Data Scientist to help us build predictive models and analyze large datasets. Requirements:
- Master's degree in Data Science, Statistics, or related field
- Experience with Python, R, SQL, and machine learning libraries
- Knowledge of TensorFlow, PyTorch, and big data technologies
- Experience with AWS, Spark, and data visualization tools
- Strong statistical analysis and communication skills
```

#### Product Manager
```
We need a Product Manager to lead our product strategy and development. Looking for:
- 5+ years of product management experience
- Experience with Agile methodologies and user research
- Strong analytical skills and data-driven decision making
- Experience with Jira, Figma, and analytics tools
- MBA or equivalent business experience preferred
```

## 🧠 How It Works

### 1. Resume Processing
- Resumes are split into chunks using recursive text splitting
- Each chunk is embedded using Gemini AI's embedding model
- Chunks are stored in ChromaDB with metadata (candidate name, ID)

### 2. Job Analysis
- Job descriptions are analyzed using Gemini AI to extract:
  - Required skills
  - Preferred skills
  - Experience level
  - Job title and industry
  - Key responsibilities

### 3. Candidate Ranking
- Job description is embedded and compared with resume chunks
- Similarity scores are calculated for each candidate
- Top candidates undergo detailed Gemini AI analysis
- Final ranking based on fit score (0-100)

### 4. Detailed Analysis
For each top candidate, the system provides:
- **Fit Score**: Overall match percentage (0-100)
- **Strengths**: Matching skills and experiences
- **Weaknesses**: Areas where candidate falls short
- **Missing Skills**: Required skills not found in resume
- **Recommendation**: Strong fit, good fit, partial fit, or weak fit
- **Reasoning**: Detailed explanation of the assessment

## 🔧 Configuration

### Environment Variables
- `GOOGLE_API_KEY`: Your Google AI API key (required)
- `CHROMA_DB_PATH`: Path to vector database storage (default: ./chroma_db)

### Customization Options

#### Adjusting Chunk Size
In `resume_processor.py`, modify the `RecursiveCharacterTextSplitter` parameters:
```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Adjust chunk size
    chunk_overlap=200,     # Adjust overlap
    length_function=len,
)
```

#### Changing Gemini AI Model
In `job_matcher.py`, modify the ChatGoogleGenerativeAI model:
```python
self.llm = ChatGoogleGenerativeAI(
    model="gemini-pro",  # Change to gemini-1.5-pro for better analysis
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1
)
```

#### Adjusting Ranking Parameters
In `job_matcher.py`, modify the similarity search:
```python
similar_docs = self.vectorstore.similarity_search_with_score(
    job_description,
    k=top_k * 2  # Adjust multiplier for more/less candidates
)
```

## 🛠️ Development

### Adding New Features

1. **New Analysis Types**: Extend the `_analyze_candidate_fit` method in `job_matcher.py`
2. **Additional Data Sources**: Modify `resume_processor.py` to handle new file formats
3. **UI Enhancements**: Add new pages or components in `app.py`

### Testing

1. **Unit Tests**: Create test files for each module
2. **Integration Tests**: Test the complete workflow
3. **Performance Testing**: Test with large datasets

### Deployment

1. **Local Development**: Use `streamlit run app.py`
2. **Production**: Deploy to Streamlit Cloud, Heroku, or similar platforms
3. **Docker**: Create a Dockerfile for containerized deployment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **ChromaDB Telemetry Warnings**
   - If you see messages like "Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given"
   - **Solution**: Use the startup script: `python start_app.py`
   - Or manually set environment variables: `set ANONYMIZED_TELEMETRY=false && set CHROMA_TELEMETRY_ENABLED=false`
   - **Note**: These warnings don't affect functionality - they're just ChromaDB trying to send usage statistics

2. **Google AI API Key Error**
   - Ensure your API key is correctly set in the `.env` file
   - Check that you have sufficient API credits
   - Verify the API key has access to Gemini AI models

3. **Database Connection Issues**
   - Ensure the `chroma_db` directory has write permissions
   - Try clearing the database and re-adding resumes

4. **Memory Issues with Large Datasets**
   - Reduce chunk size in `resume_processor.py`
   - Process resumes in smaller batches

5. **Slow Performance**
   - Consider using a more powerful Gemini AI model
   - Reduce the number of candidates analyzed
   - Implement caching for repeated queries

### Getting Help

- Check the console output for error messages
- Verify all dependencies are installed correctly
- Ensure your Google AI API key is valid and has sufficient credits

## 🎯 Future Enhancements

- [ ] PDF/DOCX text extraction
- [ ] Multi-language support
- [ ] Advanced filtering options
- [ ] Export functionality
- [ ] API endpoints for integration
- [ ] Real-time collaboration features
- [ ] Advanced analytics dashboard
- [ ] Integration with ATS systems

## 🔄 Migration from OpenAI

If you're migrating from the OpenAI version:

1. **Update dependencies**: Install the new requirements
2. **Change API key**: Replace `OPENAI_API_KEY` with `GOOGLE_API_KEY`
3. **Clear database**: The embeddings are model-specific, so clear and reprocess
4. **Test system**: Run `python test_system.py` to verify functionality

---

**Built with ❤️ using LangChain, Streamlit, and Google's Gemini AI** 