import { EmailClient } from "@azure/communication-email";
import prisma from "@/lib/prisma";
 
export async function POST(req: Request) {
 
  try {
    const connectionString = process.env.AZURE_COMMUNICATION_CONNECTION_STRING;
        if (!connectionString){
          throw new Error("AZURE_COMMUNICATION_CONNECTION_STRING is not defined")
      }
    const senderAddress=process.env.AZURE_EMAIL_SENDER;
        if (!senderAddress){
            throw new Error("AZURE_EMAIL_SENDER is not defined")
        }
    const emailClient = new EmailClient(connectionString);
 
    const { candidateIds } = await req.json(); // Get selected candidate IDs from the request body.
 
    if (!candidateIds || !Array.isArray(candidateIds) || candidateIds.length === 0) {
      return new Response(JSON.stringify({ message: "No candidate IDs provided" }), { status: 400 });
    }
 
    const candidates = await prisma.candidate.findMany({
      where: { id: { in: candidateIds } },
    });
 
    const updatedCandidates = await prisma.candidate.updateMany({
      where: {
        id: { in: candidateIds },
      },
      data: {
        status: "INVITED",
      },
    });
 
    if (candidates.length === 0) {
      return new Response(
        JSON.stringify({ message: "No candidates found with the provided IDs" }),
        { status: 404 }
      );
    }
 
    const emailPromises = candidates.map(async (candidate) => {
      const ExamDate = candidate.Exam_date
      const formattedExamDate = ExamDate? new Date(ExamDate).toLocaleString('en-US', {
        weekday: 'long',  // Optional: Adds "Monday"
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,  // Ensures 12-hour format with AM/PM
      })
      : "Exam date not specified";
 
      const emailMessage = {
        senderAddress,
        content: {
          subject: "Interview Invitation - JMAN",
          html: `
          <p>Dear ${candidate.name},</p>

            <p>Greetings from JMAN Group!</p>

            <p>We would like to block your calendar for the <strong>Level 1 Technical Interview</strong>. Kindly ensure your availability for the session. Please find your interview details below:</p>

            <h4>Interview Details</h4>
            <div style="margin-left: 20px;">
              <p><strong>Date and Time:</strong>${formattedExamDate}</p>
              <p><strong>Position:</strong> Software Engineer</p>
            </div>

            <h4>Login Credentials</h4>
            <div style="margin-left: 20px;">
              <p><strong>Username:</strong> <span style="font-weight: bold; color: #2a6cb5;">${candidate.email}</span></p>
              <p><strong>Password:</strong> <span style="font-weight: bold; color: #2a6cb5;">${candidate.tempPassword}</span></p>
            </div>

            <p>Use the link below to log in and access your interview details:</p>
            <p><a href="${candidate.Exam_URL}" style="color: #2a6cb5; text-decoration: underline;">Interview Link</a></p>

            <p>We kindly request you to confirm your attendance by selecting one of the options below:</p>

            <div style="margin: 20px 0;">
              <a href="${window.location.origin}/${candidate.id}/accept"
                style="color: #4CAF50; font-weight: bold; text-decoration: none; font-size: 16px; margin-right: 30px; display: inline-block;">
                ✔ Accept Invitation
              </a>
              <a href="${window.location.origin}/${candidate.id}/decline"
                style="color: #F44336; font-weight: bold; text-decoration: none; font-size: 16px; display: inline-block;">
                ✖ Decline Invitation
              </a>
            </div>

            <p>To ensure a smooth interview experience, please follow these guidelines:</p>
            <ul style="margin-left: 20px;">
              <li>Join at least five minutes prior to the scheduled time.</li>
              <li>Make sure you have stable internet connectivity, at least 5mbps.</li>
              <li>Check your microphone and camera settings before the start of the interview.</li>
              <li>Join the interview using a laptop/desktop only.</li>
              <li>Please join the link via web if you do not have Microsoft Teams installed.</li>
            </ul>

            <p>If you have any questions or need assistance, feel free to reach out to us.</p>

            <p>Regards,</p>
            <p>JMAN Group</p>`
        },
        recipients: {
          to: [{ address: candidate.email }],
        },
      };
 
      // Send email for each candidate
      const sendResponse = await emailClient.beginSend(emailMessage);
      const result = await sendResponse.pollUntilDone();
      // return { candidateId: candidate.id, messageId: sendResponse.messageId };
      return new Response(JSON.stringify({messageId:result}))
    });
 
    // Wait for all emails to be sent
    const emailResults = await Promise.allSettled(emailPromises);
 
    const successResults = emailResults.filter(
      (result) => result.status === "fulfilled"
    );
    const failedResults = emailResults.filter(
      (result) => result.status === "rejected"
    );
 
    return new Response(
      JSON.stringify({
        success: successResults.length,
        failed: failedResults.length,
        details: emailResults,
      }),
      { status: 200 }
    );
  } catch (error) {
    console.error("Error sending bulk emails:", error);
    const errorMessage =
    error instanceof Error ? error.message : "An unknown error occurred";
    return new Response(
      JSON.stringify({ message: "Failed to send bulk emails", error: errorMessage }),
      { status: 500 }
    );
  }
}