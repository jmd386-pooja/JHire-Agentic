import os
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
from datetime import datetime
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EmailService:
    """Service for sending personalized job selection emails to candidates."""
    
    def __init__(self):
        """Initialize email service with configuration."""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.company_name = "Jman Group"
        self.hr_contact = os.getenv("HR_CONTACT", "hr@jman-group.com")
        
        # Threading configuration for instant email sending
        self.max_workers = 10  # Maximum concurrent email threads
        self.email_timeout = 30  # Email send timeout in seconds
        
        # Gmail-specific settings
        self.use_ssl = self.smtp_server == "smtp.gmail.com" and self.smtp_port == 465
        
        if not self.sender_email or not self.sender_password:
            print("⚠️ Warning: Email credentials not configured. Email functionality will be disabled.")
            print("Please set SENDER_EMAIL and SENDER_PASSWORD in your .env file")
            print("\n📧 For Gmail users:")
            print("1. Enable 2-factor authentication")
            print("2. Generate an App Password")
            print("3. Use the App Password (not your regular password)")
            print("4. Set SENDER_PASSWORD=your_app_password")
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.sender_email and self.sender_password)
    
    def generate_job_selection_email(self, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> str:
        """Generate personalized job selection email content."""
        
        # Extract candidate information
        candidate_name = candidate_data.get("candidate_name", "Valued Candidate")
        fit_score = candidate_data.get("fit_score", 0)
        
        # Extract job information
        job_title = job_data.get("job_title", "the position")
        company_name = job_data.get("company_name", self.company_name)
        location = job_data.get("location", "our location")
        
        # Generate strengths summary
        strengths = candidate_data.get("strengths", [])
        strengths_text = ""
        if strengths:
            strengths_text = "\n\nYour key strengths that align with this role include:\n"
            for strength in strengths[:3]:  # Top 3 strengths
                strengths_text += f"• {strength}\n"
        
        # Generate email content
        email_content = f"""
Dear {candidate_name},

🎉 Congratulations! We are pleased to inform you that you have been selected for {job_title} at {company_name}.

**Selection Details:**
• Position: {job_title}
• Company: {company_name}
• Location: {location}
• Your Fit Score: {fit_score}%

{strengths_text}

**Next Steps:**
1. **Interview Scheduling**: Our HR team will contact you within 2-3 business days to schedule the next round of interviews.
2. **Documentation**: Please ensure you have the following documents ready:
   - Updated resume
   - Professional references
   - Portfolio/work samples (if applicable)
3. **Preparation**: Review the job requirements and prepare questions about the role and company.

**What to Expect:**
- Initial HR screening call
- Technical assessment (if applicable)
- Team interview
- Final decision and offer discussion

**Contact Information:**
- HR Team: {self.hr_contact}
- Company: {company_name}

**Important Notes:**
- This selection is based on your resume and initial assessment
- Final hiring decision will be made after the interview process
- Please respond to our HR team's communication within 48 hours

We are excited about the possibility of having you join our team and look forward to meeting you in person!

Best regards,
{self.company_name} HR Team

---
*This is an automated message. Please do not reply directly to this email.*
*For questions, contact: {self.hr_contact}*
        """
        
        return email_content.strip()
    
    def test_email_connection(self) -> Dict[str, Any]:
        """Test the email connection to ensure SMTP server is accessible."""
        if not self.sender_email or not self.sender_password:
            return {
                "success": False,
                "error": "Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in .env file.",
                "type": "not_configured"
            }
        
        try:
            print(f"🔍 Testing email connection to {self.smtp_server}:{self.smtp_port}...")
            
            # Handle Gmail SSL vs TLS
            if self.use_ssl:
                # Use SSL for Gmail port 465
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                # Use TLS for other ports
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.starttls()
            
            # Test login
            server.login(self.sender_email, self.sender_password)
            
            # Close connection
            server.quit()
            
            print("✅ Email connection test successful!")
            return {
                "success": True,
                "message": "Email connection test successful",
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port,
                "sender_email": self.sender_email,
                "connection_type": "SSL" if self.use_ssl else "TLS"
            }
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Authentication failed: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Provide Gmail-specific help
            if self.smtp_server == "smtp.gmail.com":
                error_msg += "\n\nFor Gmail users:"
                error_msg += "\n1. Enable 2-factor authentication in your Google account"
                error_msg += "\n2. Generate an App Password (not your regular password)"
                error_msg += "\n3. Use the App Password in SENDER_PASSWORD"
                error_msg += "\n4. Make sure 'Less secure app access' is NOT enabled"
            
            return {
                "success": False,
                "error": error_msg,
                "type": "authentication_error",
                "gmail_specific": self.smtp_server == "smtp.gmail.com"
            }
            
        except smtplib.SMTPConnectError as e:
            error_msg = f"Connection failed: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Provide connection troubleshooting
            error_msg += "\n\nTroubleshooting:"
            error_msg += f"\n• Check if {self.smtp_server}:{self.smtp_port} is accessible"
            error_msg += "\n• Verify your internet connection"
            error_msg += "\n• Check firewall settings"
            error_msg += "\n• Try different SMTP settings"
            
            return {
                "success": False,
                "error": error_msg,
                "type": "connection_error"
            }
            
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            print(f"❌ {error_msg}")
            
            # Provide SMTP troubleshooting
            error_msg += "\n\nSMTP Troubleshooting:"
            error_msg += f"\n• Verify SMTP server: {self.smtp_server}"
            error_msg += f"\n• Verify SMTP port: {self.smtp_port}"
            error_msg += "\n• Check if server requires SSL/TLS"
            error_msg += "\n• Verify server is not blocking connections"
            
            return {
                "success": False,
                "error": error_msg,
                "type": "smtp_error"
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "type": "unknown_error"
            }

    def get_email_configuration_status(self) -> Dict[str, Any]:
        """Get the current email configuration status."""
        return {
            "configured": bool(self.sender_email and self.sender_password),
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "sender_email": self.sender_email,
            "company_name": self.company_name,
            "hr_contact": self.hr_contact,
            "max_workers": self.max_workers,
            "email_timeout": self.email_timeout
        }

    def send_job_selection_email(self, candidate_email: str, candidate: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a job selection email to a single candidate with improved error handling and retry logic."""
        if not self.sender_email or not self.sender_password:
            return {
                "success": False,
                "error": "Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in .env file."
            }
        
        # Retry configuration
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Create message
                msg = MIMEMultipart()
                msg['From'] = self.sender_email
                msg['To'] = candidate_email
                msg['Subject'] = f"🎉 Congratulations! You've Been Selected for {job_data.get('job_title', 'the Position')}"
                
                # Generate email content
                email_content = self.generate_job_selection_email(candidate, job_data)
                msg.attach(MIMEText(email_content, 'plain'))  # Changed from 'html' to 'plain'
                
                # Send email with improved connection handling
                try:
                    # Create SMTP connection with timeout and proper SSL/TLS handling
                    if self.use_ssl:
                        # Use SSL for Gmail port 465
                        server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
                    else:
                        # Use TLS for other ports
                        server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                        server.starttls()
                    
                    # Login with timeout
                    server.login(self.sender_email, self.sender_password)
                    
                    # Send email
                    server.send_message(msg)
                    
                    # Close connection properly
                    server.quit()
                    
                    return {
                        "success": True,
                        "message": "Email sent successfully",
                        "candidate_email": candidate_email,
                        "candidate_name": candidate.get("candidate_name", "Unknown"),
                        "fit_score": candidate.get("fit_score", 0),
                        "rank": candidate.get("rank", "N/A"),  # Add rank information
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "attempt": attempt + 1
                    }
                    
                except smtplib.SMTPException as smtp_error:
                    # Handle SMTP-specific errors
                    error_msg = f"SMTP Error (Attempt {attempt + 1}/{max_retries}): {str(smtp_error)}"
                    print(f"⚠️ {error_msg}")
                    
                    if attempt < max_retries - 1:
                        print(f"🔄 Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return {
                            "success": False,
                            "error": f"SMTP Error after {max_retries} attempts: {str(smtp_error)}",
                            "candidate_email": candidate_email,
                            "candidate_name": candidate.get("candidate_name", "Unknown")
                        }
                        
                except Exception as conn_error:
                    # Handle connection errors
                    error_msg = f"Connection Error (Attempt {attempt + 1}/{max_retries}): {str(conn_error)}"
                    print(f"⚠️ {error_msg}")
                    
                    if attempt < max_retries - 1:
                        print(f"🔄 Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return {
                            "success": False,
                            "error": f"Connection Error after {max_retries} attempts: {str(conn_error)}",
                            "candidate_email": candidate_email,
                            "candidate_name": candidate.get("candidate_name", "Unknown")
                        }
                        
            except Exception as e:
                # Handle any other unexpected errors
                error_msg = f"Unexpected Error (Attempt {attempt + 1}/{max_retries}): {str(e)}"
                print(f"⚠️ {error_msg}")
                
                if attempt < max_retries - 1:
                    print(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"Unexpected Error after {max_retries} attempts: {str(e)}",
                        "candidate_email": candidate_email,
                        "candidate_name": candidate.get("candidate_name", "Unknown")
                    }
        
        # If we get here, all retries failed
        return {
            "success": False,
            "error": f"All {max_retries} attempts failed",
            "candidate_email": candidate_email,
            "candidate_name": candidate.get("candidate_name", "Unknown")
        }

    def send_bulk_selection_emails(self, selected_candidates: List[Dict[str, Any]], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send job selection emails to multiple candidates using parallel processing for INSTANT delivery with improved error handling."""
        if not self.sender_email or not self.sender_password:
            return {
                "success": False,
                "total_candidates": len(selected_candidates),
                "emails_sent": 0,
                "emails_failed": 0,
                "successful_sends": [],
                "failed_sends": [],
                "summary": "Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in .env file."
            }
        
        print(f"🚀 INSTANT EMAIL SENDING: Preparing to send {len(selected_candidates)} emails in parallel...")
        start_time = time.time()
        
        results = {
            "total_candidates": len(selected_candidates),
            "emails_sent": 0,
            "emails_failed": 0,
            "successful_sends": [],
            "failed_sends": [],
            "summary": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "processing_time": 0
        }
        
        # Filter candidates with email addresses
        candidates_with_email = [c for c in selected_candidates if c.get("email")]
        candidates_without_email = [c for c in selected_candidates if not c.get("email")]
        
        # Add candidates without email to failed sends
        for candidate in candidates_without_email:
            results["emails_failed"] += 1
            results["failed_sends"].append({
                "candidate_name": candidate.get("candidate_name", "Unknown"),
                "candidate_id": candidate.get("candidate_id", "Unknown"),
                "error": "No email address found in candidate data",
                "fit_score": candidate.get("fit_score", 0),
                "rank": candidate.get("rank", "N/A"),
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
        
        if not candidates_with_email:
            results["summary"] = "❌ FAILURE: No candidates have email addresses."
            results["success"] = False
            return results
        
        print(f"📧 Sending emails to {len(candidates_with_email)} candidates with email addresses...")
        
        # Use ThreadPoolExecutor for parallel email sending with improved error handling
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(candidates_with_email))) as executor:
            # Submit all email sending tasks
            future_to_candidate = {
                executor.submit(self._send_single_email_with_timeout, candidate, job_data): candidate 
                for candidate in candidates_with_email
            }
            
            # Process completed emails in real-time
            for future in as_completed(future_to_candidate, timeout=self.email_timeout * len(candidates_with_email)):
                candidate = future_to_candidate[future]
                try:
                    email_result = future.result(timeout=self.email_timeout)
                    
                    if email_result["success"]:
                        results["emails_sent"] += 1
                        # Ensure rank information is included
                        email_result["rank"] = candidate.get("rank", "N/A")
                        results["successful_sends"].append(email_result)
                        print(f"✅ INSTANT: Email sent to {email_result['candidate_name']} ({email_result['candidate_email']}) - Attempt {email_result.get('attempt', 1)}")
                    else:
                        results["emails_failed"] += 1
                        results["failed_sends"].append({
                            "candidate_name": candidate.get("candidate_name", "Unknown"),
                            "candidate_id": candidate.get("candidate_id", "Unknown"),
                            "email": candidate.get("email"),
                            "fit_score": candidate.get("fit_score", 0),
                            "rank": candidate.get("rank", "N/A"),
                            "error": email_result.get("error", "Unknown error"),
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        print(f"❌ FAILED: Email to {candidate.get('candidate_name', 'Unknown')} - {email_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    results["emails_failed"] += 1
                    results["failed_sends"].append({
                        "candidate_name": candidate.get("candidate_name", "Unknown"),
                        "candidate_id": candidate.get("candidate_id", "Unknown"),
                        "email": candidate.get("email"),
                        "fit_score": candidate.get("fit_score", 0),
                        "rank": candidate.get("rank", "N/A"),
                        "error": f"Thread execution error: {str(e)}",
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    print(f"❌ THREAD ERROR: Email to {candidate.get('candidate_name', 'Unknown')} - {str(e)}")
        
        # Calculate processing time
        end_time = time.time()
        results["processing_time"] = round(end_time - start_time, 2)
        
        # Generate summary
        if results["emails_failed"] == 0:
            results["summary"] = f"✅ SUCCESS: All {results['emails_sent']} emails sent INSTANTLY in {results['processing_time']}s!"
            results["success"] = True
        elif results["emails_sent"] == 0:
            results["summary"] = f"❌ FAILURE: All {results['emails_failed']} emails failed to send."
            results["success"] = False
        else:
            results["summary"] = f"⚠️ PARTIAL: {results['emails_sent']} emails sent INSTANTLY in {results['processing_time']}s, {results['emails_failed']} failed."
            results["success"] = False
        
        print(f"\n🎯 INSTANT EMAIL RESULTS:")
        print(f"   ✅ Sent: {results['emails_sent']}")
        print(f"   ❌ Failed: {results['emails_failed']}")
        print(f"   ⏱️  Time: {results['processing_time']}s")
        print(f"   📊 Summary: {results['summary']}")
        
        return results

    def _send_single_email_with_timeout(self, candidate: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single email with timeout protection for thread safety."""
        try:
            return self.send_job_selection_email(candidate.get("email"), candidate, job_data)
        except Exception as e:
            return {
                "success": False,
                "error": f"Email sending error: {str(e)}",
                "candidate_email": candidate.get("email"),
                "candidate_name": candidate.get("candidate_name", "Unknown")
            }

    def send_immediate_selection_emails(self, selected_candidates: List[Dict[str, Any]], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send job selection emails immediately using INSTANT parallel processing."""
        print("🚀 STARTING INSTANT EMAIL SENDING PROCESS...")
        print(f"📧 Preparing to send emails to {len(selected_candidates)} candidates INSTANTLY...")
        
        # Send emails using the enhanced parallel system
        results = self.send_bulk_selection_emails(selected_candidates, job_data)
        
        # Generate detailed report
        detailed_report = self.get_detailed_email_report(results)
        
        # Print results to console with enhanced formatting
        print("\n" + "="*80)
        print("📧 INSTANT EMAIL SENDING RESULTS")
        print("="*80)
        print(detailed_report)
        print("="*80)
        
        # Add report to results
        results["detailed_report"] = detailed_report
        
        # Add enhanced summary information
        results["enhanced_summary"] = self._generate_enhanced_summary(results)
        
        return results

    def send_automatic_selection_emails(self, selected_candidates: List[Dict[str, Any]], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send job selection emails automatically without any user interaction - triggered immediately after candidate matching."""
        print("🤖 AUTOMATIC EMAIL SENDING TRIGGERED - No user interaction required!")
        print(f"📧 Automatically sending emails to {len(selected_candidates)} matched candidates...")
        
        # Validate email configuration first
        if not self.is_configured():
            return {
                "success": False,
                "total_candidates": len(selected_candidates),
                "emails_sent": 0,
                "emails_failed": len(selected_candidates),
                "successful_sends": [],
                "failed_sends": [],
                "summary": "❌ AUTOMATIC EMAIL FAILED: Email service not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in .env file.",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": 0,
                "error": "Email service not configured"
            }
        
        # Test email connection before sending
        print("🔍 Testing email connection before sending...")
        connection_test = self.test_email_connection()
        
        if not connection_test["success"]:
            error_msg = f"❌ AUTOMATIC EMAIL FAILED: Email connection test failed - {connection_test['error']}"
            print(error_msg)
            
            # Add all candidates to failed sends
            failed_sends = []
            for candidate in selected_candidates:
                failed_sends.append({
                    "candidate_name": candidate.get("candidate_name", "Unknown"),
                    "candidate_id": candidate.get("candidate_id", "Unknown"),
                    "email": candidate.get("email"),
                    "fit_score": candidate.get("fit_score", 0),
                    "rank": candidate.get("rank", "N/A"),
                    "error": f"Connection test failed: {connection_test['error']}",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            
            return {
                "success": False,
                "total_candidates": len(selected_candidates),
                "emails_sent": 0,
                "emails_failed": len(selected_candidates),
                "successful_sends": [],
                "failed_sends": failed_sends,
                "summary": error_msg,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": 0,
                "error": connection_test["error"],
                "connection_test": connection_test
            }
        
        print("✅ Email connection test successful! Proceeding with email sending...")
        
        # Filter candidates with email addresses
        candidates_with_email = [c for c in selected_candidates if c.get("email")]
        candidates_without_email = [c for c in selected_candidates if not c.get("email")]
        
        if not candidates_with_email:
            return {
                "success": False,
                "total_candidates": len(selected_candidates),
                "emails_sent": 0,
                "emails_failed": len(selected_candidates),
                "successful_sends": [],
                "failed_sends": [{
                    "candidate_name": c.get("candidate_name", "Unknown"),
                    "candidate_id": c.get("candidate_id", "Unknown"),
                    "email": c.get("email"),
                    "fit_score": c.get("fit_score", 0),
                    "rank": c.get("rank", "N/A"),
                    "error": "No email address found in candidate data",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                } for c in candidates_without_email],
                "summary": "❌ AUTOMATIC EMAIL FAILED: No candidates have email addresses.",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": 0,
                "error": "No email addresses found"
            }
        
        print(f"📧 Found {len(candidates_with_email)} candidates with email addresses for automatic sending...")
        
        # Send emails using the enhanced parallel system
        start_time = time.time()
        results = self.send_bulk_selection_emails(selected_candidates, job_data)
        end_time = time.time()
        
        # Add automatic sending metadata
        results["automatic_sending"] = True
        results["triggered_by"] = "automatic_candidate_matching"
        results["user_interaction_required"] = False
        results["processing_time"] = round(end_time - start_time, 2)
        results["connection_test"] = connection_test
        
        # Generate enhanced summary for automatic sending
        results["enhanced_summary"] = self._generate_automatic_sending_summary(results)
        
        # Log automatic sending results
        print(f"\n🤖 AUTOMATIC EMAIL SENDING COMPLETED:")
        print(f"   ✅ Sent: {results['emails_sent']}")
        print(f"   ❌ Failed: {results['emails_failed']}")
        print(f"   ⏱️  Time: {results['processing_time']}s")
        print(f"   📊 Summary: {results['summary']}")
        
        return results

    def _generate_enhanced_summary(self, email_results: Dict[str, Any]) -> str:
        """Generate an enhanced summary with actionable insights."""
        total = email_results['total_candidates']
        sent = email_results['emails_sent']
        failed = email_results['emails_failed']
        
        if total == 0:
            return "No candidates to process"
        
        success_rate = (sent / total) * 100
        
        summary = f"""
🎯 ENHANCED EMAIL SUMMARY
{'='*50}
📊 OVERALL RESULTS:
• Total Candidates: {total}
• Emails Sent Successfully: {sent} ✅
• Emails Failed: {failed} ❌
• Success Rate: {success_rate:.1f}%

📈 ANALYSIS:
"""
        
        if success_rate == 100:
            summary += "🎉 PERFECT SUCCESS: All emails sent successfully!"
        elif success_rate >= 80:
            summary += "✅ EXCELLENT: High success rate with minor issues"
        elif success_rate >= 60:
            summary += "⚠️ GOOD: Moderate success rate, some issues to address"
        elif success_rate >= 40:
            summary += "⚠️ FAIR: Below average success rate, needs attention"
        else:
            summary += "❌ POOR: Low success rate, significant issues to resolve"
        
        # Add specific insights
        if failed > 0:
            summary += f"\n\n🔍 FAILURE ANALYSIS:"
            summary += f"\n• {failed} candidates did not receive emails"
            summary += f"\n• Common failure reasons:"
            
            # Analyze failure reasons
            failure_reasons = {}
            for failed_send in email_results.get('failed_sends', []):
                reason = failed_send.get('error', 'Unknown error')
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            for reason, count in failure_reasons.items():
                summary += f"\n  - {reason}: {count} occurrences"
        
        # Add recommendations
        summary += f"\n\n💡 RECOMMENDATIONS:"
        if failed == 0:
            summary += "\n• All emails sent successfully - no action needed"
        elif failed <= 2:
            summary += "\n• Minor issues - consider manual follow-up for failed sends"
        elif failed <= 5:
            summary += "\n• Moderate issues - review email configuration and retry failed sends"
        else:
            summary += "\n• Significant issues - investigate email configuration and system setup"
        
        if failed > 0:
            summary += f"\n• Retry failed emails using the 'Send Failed Emails Again' button"
            summary += f"\n• Check email configuration if multiple failures occur"
        
        return summary.strip()

    def _generate_automatic_sending_summary(self, email_results: Dict[str, Any]) -> str:
        """Generate a summary specifically for automatic email sending."""
        total = email_results['total_candidates']
        sent = email_results['emails_sent']
        failed = email_results['emails_failed']
        
        if total == 0:
            return "No candidates to process automatically"
        
        success_rate = (sent / total) * 100
        
        summary = f"""
🤖 AUTOMATIC EMAIL SENDING SUMMARY
{'='*50}
📊 AUTOMATIC RESULTS:
• Total Candidates Matched: {total}
• Emails Sent Automatically: {sent} ✅
• Emails Failed: {failed} ❌
• Success Rate: {success_rate:.1f}%
• Processing Time: {email_results.get('processing_time', 0)}s

🎯 AUTOMATIC PROCESSING:
• Triggered by: Candidate matching completion
• User Interaction: Not required
• Sending Method: Parallel processing
• Status: {'✅ COMPLETED' if sent > 0 else '❌ FAILED'}

📈 ANALYSIS:
"""
        
        if success_rate == 100:
            summary += "🎉 PERFECT SUCCESS: All emails sent automatically without user intervention!"
        elif success_rate >= 80:
            summary += "✅ EXCELLENT: High success rate with automatic sending"
        elif success_rate >= 60:
            summary += "⚠️ GOOD: Moderate success rate, some manual follow-up may be needed"
        elif success_rate >= 40:
            summary += "⚠️ FAIR: Below average success rate, manual intervention recommended"
        else:
            summary += "❌ POOR: Low success rate, manual email sending required"
        
        # Add specific insights for automatic sending
        if failed > 0:
            summary += f"\n\n🔍 FAILURE ANALYSIS:"
            summary += f"\n• {failed} candidates did not receive automatic emails"
            
            # Analyze failure reasons
            failure_reasons = {}
            for failed_send in email_results.get('failed_sends', []):
                reason = failed_send.get('error', 'Unknown error')
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            for reason, count in failure_reasons.items():
                summary += f"\n  - {reason}: {count} occurrences"
        
        # Add recommendations for automatic sending
        summary += f"\n\n💡 RECOMMENDATIONS:"
        if failed == 0:
            summary += "\n• All emails sent automatically - no action needed"
        elif failed <= 2:
            summary += "\n• Minor issues - automatic system working well"
        elif failed <= 5:
            summary += "\n• Moderate issues - review email configuration"
        else:
            summary += "\n• Significant issues - investigate email system setup"
        
        if failed > 0:
            summary += f"\n• Manual retry available for failed emails"
            summary += f"\n• Check email configuration if multiple failures occur"
        
        summary += f"\n\n🚀 AUTOMATIC SYSTEM STATUS:"
        summary += f"\n• System: Fully automated"
        summary += f"\n• User Action: Not required"
        summary += f"\n• Next Step: Monitor email delivery and candidate responses"
        
        return summary.strip()
    
    def get_detailed_email_report(self, email_results: Dict[str, Any]) -> str:
        """Generate a detailed report of email sending results."""
        report = f"""
📧 EMAIL SENDING REPORT
{'='*50}
Timestamp: {email_results.get('timestamp', 'N/A')}
Total Candidates: {email_results['total_candidates']}
Emails Sent: {email_results['emails_sent']}
Emails Failed: {email_results['emails_failed']}

📊 SUMMARY
{email_results.get('summary', 'No summary available')}

✅ SUCCESSFUL SENDS ({email_results['emails_sent']})
{'-'*30}"""
        
        if email_results['successful_sends']:
            for success in email_results['successful_sends']:
                rank = success.get('rank', 'N/A')
                report += f"""
• {success['candidate_name']} (Rank #{rank})
  📧 {success.get('email', 'N/A')}
  🎯 Fit Score: {success.get('fit_score', 0)}%
  ✅ Sent at: {success.get('timestamp', 'N/A')}"""
        else:
            report += "\nNo successful sends."
        
        if email_results['failed_sends']:
            report += f"""

❌ FAILED SENDS ({email_results['emails_failed']})
{'-'*30}"""
            for failed in email_results['failed_sends']:
                rank = failed.get('rank', 'N/A')
                report += f"""
• {failed['candidate_name']} (Rank #{rank})
  📧 {failed.get('email', 'N/A')}
  🎯 Fit Score: {failed.get('fit_score', 0)}%
  ❌ Error: {failed.get('error', 'Unknown error')}
  ⏰ Failed at: {failed.get('timestamp', 'N/A')}"""
        
        return report.strip()
    
    def generate_email_template_preview(self, candidate_data: Dict[str, Any], job_data: Dict[str, Any]) -> str:
        """Generate a preview of the email that would be sent."""
        return self.generate_job_selection_email(candidate_data, job_data)
