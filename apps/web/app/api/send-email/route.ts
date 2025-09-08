import { EmailClient } from "@azure/communication-email";
import prisma from "@/lib/prisma";

export async function POST(req: Request) {
  try {
    const connectionString = process.env.AZURE_COMMUNICATION_CONNECTION_STRING;
    if (!connectionString) {
      throw new Error("AZURE_COMMUNICATION_CONNECTION_STRING is not defined");
    }
    const emailClient = new EmailClient(connectionString);

    const senderAddress = process.env.AZURE_EMAIL_SENDER;
    if (!senderAddress) {
      throw new Error("AZURE_EMAIL_SENDER is not defined");
    }

    const { id, to, subject, htmlContent } = await req.json();

    // Validate input
    if (!id || !to || !subject || !htmlContent) {
      return new Response(JSON.stringify({ message: "Missing required fields" }), { status: 400 });
    }

    // Prepare email message
    const emailMessage = {
      senderAddress,
      content: {
        subject: subject,
        html: htmlContent,
      },
      recipients: {
        to: [{ address: to }],
      },
    };
    // Send the email
    const response = await emailClient.beginSend(emailMessage);
    const result = await response.pollUntilDone();
    

    // Ensure email was sent successfully (response.messageId confirms success)
    if (!response) {
      throw new Error("Failed to send email");
    }

    // Update the candidate's status to 'invited'
    const updatedCandidate = await prisma.candidate.update({
      where: { id: id },
      data: { status: "INVITED" }, // Change status from 'pending' to 'invited'
    });

    return new Response(
      JSON.stringify({
        messageId: result,
        message: "Email sent successfully, status updated to 'invited'",
      }),
      { status: 200 }
    );
  } catch (error) {
    console.error("Error:", error);
    const errorMessage =
    error instanceof Error ? error.message : "An unknown error occurred";
    return new Response(
      JSON.stringify({ message: "An error occurred", error: errorMessage }),
      { status: 500 }
    );
  }
}