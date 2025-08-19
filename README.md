
# Candidate Management and Assessment Platform

This project is a **Next.js** application designed to streamline candidate management and assessments for HR teams. It includes features like Excel-based candidate creation, AI-powered personalized assessments, and robust monitoring for assessment integrity.

---

## Features

### User Authentication
- **Login and Registration**: Basic authentication for users.
- **SSO Integration**: Phase 2 will incorporate Single Sign-On (SSO).

### Candidate Management
- **Excel File Upload**: 
  - HR teams can upload a standardized Excel file with candidate data.
  - Download candidate resumes from SharePoint using provided URLs.
- **Candidate Creation**: 
  - Extract candidate details from the uploaded Excel file.
  - Assign avatars to candidates and embed resumes using OpenAI embeddings.
  - Store candidate data and embeddings in ChromaDB.
- **Candidate Listing**: 
  - Card-based UI to display candidate profiles.
  - Email-triggering functionality for individual and bulk actions.

### Candidate Assessment Workflow
- **Email-Triggered Login**:
  - Candidates log in via credentials shared in an email.
  - Verification to ensure access authorization.
- **Assessment Platform**:
  - Landing page with instructions and a "Start" button.
  - Full-screen assessments with:
    - Camera activation.
    - Screen/audio recording.
    - Tab-switching warnings.
    - Unauthorized activity detection.
- **Question Generation**:
  - Generate personalized questions using OpenAI embeddings of the resume and job description.
  - Dynamically adapt questions based on candidate responses.
  - Interactive Q&A interface with an avatar.
- **Coding Challenges**:
  - Integrated coding editor with validation and feedback.

### Key Features
- Integration with SharePoint for resume management.
- AI-powered dynamic assessment workflows.
- Advanced monitoring for anti-cheating during assessments.
- Modular and scalable design for future enhancements.

---

## Installation and Setup

### Prerequisites
- **Node.js**: v16.x or later
- **npm** or **yarn**
- Access to an OpenAI API key
- SharePoint credentials for resume retrieval
- ChromaDB instance for embedding storage

### Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-repo-url/candidate-platform.git
   cd candidate-platform
   ```

2. **Install Dependencies**:
   Use the following command to install the required packages:
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Setup Environment Variables**:
   Create a `.env.local` file in the project root directory. Include the following environment variables in the file:
   ```env
   NEXT_PUBLIC_OPENAI_API_KEY=your-openai-api-key
   SHAREPOINT_BASE_URL=your-sharepoint-url
   CHROMADB_ENDPOINT=your-chromadb-endpoint
   AUTH_SECRET=your-auth-secret
   ```

4. **Run the Development Server**:
   Start the application locally using:
   ```bash
   npm run dev
   # or
   yarn dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser to view the application.

---

## File Structure

Below is an overview of the project's file organization:

```
├── components/
│   ├── Auth/                 # Components related to user authentication
│   ├── Candidates/           # Components for candidate listing and details
│   ├── Assessments/          # Components for the assessment platform
│   └── Shared/               # Reusable components (e.g., headers, footers)
├── pages/
│   ├── api/                  # API routes for server-side processing
│   ├── auth/                 # Login and registration pages
│   ├── candidates/           # Candidate management pages
│   ├── assessments/          # Assessment-related pages
│   └── index.js              # Home page
├── public/                   # Static assets (images, icons, etc.)
├── styles/                   # Global and component-specific styles
├── utils/                    # Utility functions and API integrations
│   ├── chromadb.js           # ChromaDB connection and queries
│   ├── openai.js             # OpenAI API interactions
│   └── sharepoint.js         # SharePoint integration for resume management
├── .env.local                # Environment variables (not included in the repo)
├── next.config.js            # Next.js configuration
├── package.json              # Project dependencies and scripts
└── README.md                 # Documentation
```

---

## Key Libraries Used
- **Next.js**: Framework for server-rendered React applications.
- **TailwindCSS**: Styling framework for responsive and modern UI design.
- **NextAuth.js**: Authentication library for Next.js.
- **OpenAI API**: AI-powered embeddings and question generation.
- **ChromaDB**: Vector database for storing embeddings.
- **Axios**: HTTP client for API integrations.
- **SharePoint REST API**: To fetch resumes using provided URLs.

---

## Future Enhancements
- SSO integration for corporate authentication.
- Real-time analysis of assessment results.
- Enhanced monitoring with machine learning-based fraud detection.

---

## Contributing
1. Fork the repository.
2. Create a new feature branch.
3. Commit your changes.
4. Push to the branch and open a Pull Request.

---

## License
This project is licensed under the [](LICENSE).

---

## Contact
For issues or inquiries, contact us at **....@Jmangroup.com**.