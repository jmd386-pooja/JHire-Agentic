import axios from "axios";
import * as dotenv from "dotenv";
import FormData from "form-data";
import { NextRequest } from "next/server";

dotenv.config();

const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;

const sharepointHost = process.env.SHAREPOINT_HOST!;
const siteName = process.env.SHAREPOINT_SITE_NAME!;
const driveName = process.env.SHAREPOINT_DRIVE_NAME!;
const resumeFolderId = process.env.RESUME_FOLDER_ID!; // The folder that contains resumes

async function getGraphToken(): Promise<string> {
  const res = await axios.post(
    `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
    new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      scope: "https://graph.microsoft.com/.default",
      grant_type: "client_credentials",
    }).toString(),
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }
  );
  return res.data.access_token as string;
}

async function fetchSiteAndDriveId(token: string) {
  // Resolve site -> siteId
  const siteRes = await axios.get(
    `https://graph.microsoft.com/v1.0/sites/${sharepointHost}:/sites/${siteName}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const siteId = siteRes.data.id as string;

  // Get drive ID by name
  const driveRes = await axios.get(
    `https://graph.microsoft.com/v1.0/sites/${siteId}/drives`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const drive = (driveRes.data.value as any[]).find(
    (d: any) => d.name === driveName
  );
  const driveId = drive?.id as string;

  if (!driveId)
    throw new Error(`Drive "${driveName}" not found on site ${siteName}`);

  return { siteId, driveId };
}

async function fetchPdfFiles(driveId: string, token: string) {
  // List children of the configured resume folder
  const listRes = await axios.get(
    `https://graph.microsoft.com/v1.0/drives/${driveId}/items/${resumeFolderId}/children`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  const items = listRes.data?.value as any[];
  // Filter to PDFs (has file facet + mime)
  const pdfs = items.filter(
    (it: any) =>
      it.file &&
      (it.file.mimeType === "application/pdf" ||
        String(it.name).toLowerCase().endsWith(".pdf"))
  );

  return pdfs;
}

/**
 * Post the raw PDF bytes to /api/extractResumeDetails as multipart/form-data
 * under the key "files" — this matches how the upload UI posts local files.
 */
async function processResume(
  downloadUrl: string,
  fileName: string,
  uploadUrl: string
) {
  // Download PDF from the Graph-provided link
  const pdfRes = await axios.get(downloadUrl, { responseType: "arraybuffer" });
  const pdfBuffer = Buffer.from(pdfRes.data);

  // Build multipart with the exact "files" key this API expects
  const form = new FormData();
  form.append("files", pdfBuffer, {
    filename: fileName,
    contentType: "application/pdf",
  });
  // Optional: include metadata if your API accepts it (safe to omit)
  form.append("source", "sharepoint");
  form.append("originalFileName", fileName);

  // Post to our internal API
  await axios.post(uploadUrl, form, {
    headers: form.getHeaders(),
    // Don’t gzip the body here; API will parse multipart
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
  });
}

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const push = (obj: any) =>
        controller.enqueue(encoder.encode(JSON.stringify(obj) + "\n"));

      try {
        const origin = new URL(request.url).origin;
        const uploadUrl = `${origin}/api/extractResumeDetails`;
        const categorizeUrl = `${origin}/api/CategorizeResume`;

        const token = await getGraphToken();
        const { driveId } = await fetchSiteAndDriveId(token);
        const files = await fetchPdfFiles(driveId, token);

        push({ type: "start", total: files.length });

        let index = 0;
        for (const file of files) {
          const downloadUrl = file["@microsoft.graph.downloadUrl"] as string;
          const fileName = file.name as string;

          await processResume(downloadUrl, fileName, uploadUrl);

          index++;
          push({ type: "item", index, total: files.length, file: fileName });
        }

        // Kick categorization when all uploads are ingested
        push({ type: "categorizing" });
        await axios.get(categorizeUrl);

        push({ type: "complete", total: files.length });
        controller.close();
      } catch (err: any) {
        const message = err?.message || "Unknown error";
        push({ type: "error", message });
        controller.error(err);
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson",
      "Cache-Control": "no-store",
    },
  });
}
