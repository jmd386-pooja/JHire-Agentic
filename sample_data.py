import json
from resume_processor import ResumeProcessor

# Sample resumes for testing
SAMPLE_RESUMES = [
    {
        "name": "John Smith",
        "text": """
JOHN SMITH
Software Engineer
john.smith@email.com | (555) 123-4567 | linkedin.com/in/johnsmith

PROFESSIONAL SUMMARY
Experienced software engineer with 5+ years developing scalable web applications using Python, JavaScript, and cloud technologies. Passionate about clean code, system design, and mentoring junior developers.

TECHNICAL SKILLS
• Programming Languages: Python, JavaScript, TypeScript, Java, SQL
• Frameworks & Libraries: Django, React, Node.js, Express, FastAPI
• Cloud & DevOps: AWS, Docker, Kubernetes, CI/CD, Git
• Databases: PostgreSQL, MongoDB, Redis
• Tools: VS Code, Jira, Confluence, Slack

WORK EXPERIENCE

Senior Software Engineer | TechCorp Inc. | 2021 - Present
• Led development of microservices architecture serving 1M+ users
• Mentored 3 junior developers and conducted code reviews
• Implemented CI/CD pipeline reducing deployment time by 60%
• Collaborated with product team to define technical requirements

Software Engineer | StartupXYZ | 2019 - 2021
• Developed full-stack web applications using React and Django
• Optimized database queries improving performance by 40%
• Participated in agile development process with 2-week sprints
• Contributed to open-source projects and technical blog posts

EDUCATION
Bachelor of Science in Computer Science
University of Technology | 2019

CERTIFICATIONS
• AWS Certified Developer Associate
• Google Cloud Professional Developer
"""
    },
    {
        "name": "Sarah Johnson",
        "text": """
SARAH JOHNSON
Data Scientist
sarah.johnson@email.com | (555) 987-6543 | linkedin.com/in/sarahjohnson

PROFESSIONAL SUMMARY
Data scientist with expertise in machine learning, statistical analysis, and big data processing. Proven track record of delivering insights that drive business decisions and improve operational efficiency.

TECHNICAL SKILLS
• Programming Languages: Python, R, SQL, Scala
• Machine Learning: TensorFlow, PyTorch, Scikit-learn, XGBoost
• Big Data: Spark, Hadoop, Kafka, Airflow
• Visualization: Tableau, Power BI, Matplotlib, Seaborn
• Cloud: AWS, Azure, Google Cloud Platform

WORK EXPERIENCE

Senior Data Scientist | DataTech Solutions | 2020 - Present
• Developed ML models improving customer retention by 25%
• Led team of 4 data scientists on predictive analytics projects
• Built real-time data processing pipeline using Apache Kafka
• Presented findings to C-suite executives and stakeholders

Data Analyst | Analytics Corp | 2018 - 2020
• Created dashboards and reports for business intelligence
• Performed statistical analysis on customer behavior data
• Automated data cleaning processes saving 20 hours/week
• Collaborated with marketing team on A/B testing campaigns

EDUCATION
Master of Science in Data Science
Stanford University | 2018

Bachelor of Science in Mathematics
University of California | 2016

CERTIFICATIONS
• Google Cloud Professional Data Engineer
• AWS Machine Learning Specialty
"""
    },
    {
        "name": "Michael Chen",
        "text": """
MICHAEL CHEN
Product Manager
michael.chen@email.com | (555) 456-7890 | linkedin.com/in/michaelchen

PROFESSIONAL SUMMARY
Strategic product manager with 6+ years experience launching successful products from concept to market. Skilled in user research, data analysis, and cross-functional team leadership.

TECHNICAL SKILLS
• Product Management: Agile, Scrum, Kanban, Jira, Confluence
• Analytics: Google Analytics, Mixpanel, Amplitude, SQL
• Design: Figma, Sketch, InVision, User Research
• Programming: Python, SQL, HTML/CSS (basic)
• Tools: Slack, Zoom, Notion, Airtable

WORK EXPERIENCE

Senior Product Manager | ProductHub | 2021 - Present
• Led product strategy for B2B SaaS platform with $10M ARR
• Managed team of 8 engineers, designers, and analysts
• Increased user engagement by 35% through feature optimization
• Conducted user interviews and usability testing sessions

Product Manager | StartupABC | 2019 - 2021
• Launched mobile app reaching 100K+ downloads in first year
• Defined product roadmap and prioritized feature development
• Collaborated with engineering team on technical requirements
• Analyzed user feedback and market trends for product decisions

Associate Product Manager | TechGiant | 2017 - 2019
• Supported senior PMs on enterprise software products
• Created user stories and acceptance criteria
• Participated in sprint planning and retrospectives
• Conducted competitive analysis and market research

EDUCATION
Master of Business Administration
Harvard Business School | 2017

Bachelor of Science in Engineering
MIT | 2015

CERTIFICATIONS
• Certified Scrum Product Owner (CSPO)
• Google Analytics Individual Qualification
"""
    },
    {
        "name": "Emily Rodriguez",
        "text": """
EMILY RODRIGUEZ
UX/UI Designer
emily.rodriguez@email.com | (555) 321-6547 | linkedin.com/in/emilyrodriguez

PROFESSIONAL SUMMARY
Creative UX/UI designer with 4+ years creating user-centered digital experiences. Expertise in design systems, user research, and prototyping. Passionate about accessibility and inclusive design.

TECHNICAL SKILLS
• Design Tools: Figma, Sketch, Adobe Creative Suite, InVision
• Prototyping: Framer, Principle, ProtoPie, Figma Prototyping
• User Research: UserTesting, Hotjar, Google Analytics
• Programming: HTML, CSS, JavaScript (basic), React (basic)
• Tools: Notion, Slack, Zeplin, Abstract

WORK EXPERIENCE

Senior UX Designer | DesignStudio | 2020 - Present
• Led design for mobile app with 500K+ active users
• Established design system used across 5 product teams
• Conducted user research and usability testing sessions
• Mentored 2 junior designers and provided design critiques

UX Designer | CreativeAgency | 2018 - 2020
• Designed websites and mobile apps for 15+ clients
• Created wireframes, prototypes, and high-fidelity mockups
• Collaborated with developers on design implementation
• Participated in client presentations and design workshops

Junior Designer | StartupXYZ | 2017 - 2018
• Assisted senior designers on various client projects
• Created social media graphics and marketing materials
• Conducted competitive analysis and user research
• Maintained design asset libraries and style guides

EDUCATION
Bachelor of Fine Arts in Graphic Design
Parsons School of Design | 2017

CERTIFICATIONS
• Google UX Design Professional Certificate
• Nielsen Norman Group UX Certification
"""
    },
    {
        "name": "David Kim",
        "text": """
DAVID KIM
DevOps Engineer
david.kim@email.com | (555) 789-1234 | linkedin.com/in/davidkim

PROFESSIONAL SUMMARY
DevOps engineer with 5+ years experience in infrastructure automation, cloud deployment, and system reliability. Expert in CI/CD pipelines, containerization, and monitoring solutions.

TECHNICAL SKILLS
• Cloud Platforms: AWS, Azure, Google Cloud Platform
• Containerization: Docker, Kubernetes, Helm
• CI/CD: Jenkins, GitLab CI, GitHub Actions, ArgoCD
• Infrastructure: Terraform, Ansible, CloudFormation
• Monitoring: Prometheus, Grafana, ELK Stack, Datadog
• Programming: Python, Bash, Go, JavaScript

WORK EXPERIENCE

Senior DevOps Engineer | CloudTech | 2021 - Present
• Managed infrastructure serving 10M+ users across 3 regions
• Implemented GitOps workflow reducing deployment time by 70%
• Led migration from on-premise to cloud-native architecture
• Mentored 3 junior DevOps engineers and conducted training

DevOps Engineer | TechStartup | 2019 - 2021
• Built CI/CD pipelines for microservices architecture
• Automated infrastructure provisioning using Terraform
• Implemented monitoring and alerting for production systems
• Collaborated with development teams on deployment strategies

System Administrator | IT Solutions | 2017 - 2019
• Managed Linux servers and network infrastructure
• Automated system administration tasks using Python scripts
• Implemented backup and disaster recovery procedures
• Provided technical support and troubleshooting

EDUCATION
Bachelor of Science in Computer Science
University of Washington | 2017

CERTIFICATIONS
• AWS Certified DevOps Engineer Professional
• Kubernetes Administrator (CKA)
• Terraform Associate
"""
    }
]

def populate_sample_data():
    """Populate the database with sample resumes."""
    processor = ResumeProcessor()
    
    print("Adding sample resumes to the database...")
    
    for resume in SAMPLE_RESUMES:
        try:
            result = processor.process_resume(
                resume["text"],
                resume["name"]
            )
            print(f"✓ {result}")
        except Exception as e:
            print(f"✗ Error processing {resume['name']}: {str(e)}")
    
    total_resumes = processor.get_total_resumes()
    print(f"\n✅ Successfully added {total_resumes} resumes to the database!")
    print("You can now run the Streamlit app to test job matching.")

if __name__ == "__main__":
    populate_sample_data() 