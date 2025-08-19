import axios from 'axios';
import { spawn } from 'child_process';
import * as dotenv from 'dotenv';
import FormData from 'form-data';

dotenv.config();

const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;

const sharepointHost = process.env.SHAREPOINT_HOST!;
const siteName = process.env.SHAREPOINT_SITE_NAME!;
const driveName = process.env.SHAREPOINT_DRIVE_NAME!;
// const folderPath = process.env.SHAREPOINT_FOLDER_PATH!;

const resumeFolderId = process.env.RESUME_FOLDER_ID!;
// const folderPath = "Documents/CoE/DS%20%26%20AI/JHire/Resume";

const uploadUrl = 'http://localhost:3000/api/extractResumeDetails';

async function getGraphToken(): Promise<string> {
  const res = await axios.post(
    `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
    new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      scope: 'https://graph.microsoft.com/.default',
      grant_type: 'client_credentials',
    }),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  );
  return res.data.access_token;
}

async function fetchSiteAndDriveId(graphToken: string) {
  // Get site ID
  const siteRes = await axios.get(
    `https://graph.microsoft.com/v1.0/sites/${sharepointHost}:/sites/${siteName}`,
    { headers: { Authorization: `Bearer ${graphToken}` } }
  );
  const siteId = siteRes.data.id;

  // Get drive ID
  const driveRes = await axios.get(
    `https://graph.microsoft.com/v1.0/sites/${siteId}/drives`,
    { headers: { Authorization: `Bearer ${graphToken}` } }
  );
  const drive = driveRes.data.value.find((d: any) => d.name === driveName);
  const driveId = drive?.id;

  return { siteId, driveId };
}

async function fetchPdfFiles(siteId: string, driveId: string, token: string) {
  const res = await axios.get(
  `https://graph.microsoft.com/v1.0/drives/${driveId}/items/${resumeFolderId}/children`,
  { headers: { Authorization: `Bearer ${token}` } }
);


  return res.data.value.filter((file: any) => file.name.endsWith('.pdf'));
}

async function processResume(downloadUrl: string, fileName: string) {
  try {
    const pdfRes = await axios.get(downloadUrl, { responseType: 'arraybuffer' });
    const pdfBuffer = Buffer.from(pdfRes.data);

    const python = spawn('python', ['scripts/extract_resume.py']);
    let stdout = '';
    let stderr = '';

    python.stdin.write(pdfBuffer);
    python.stdin.end();

    python.stdout.on('data', (data) => (stdout += data.toString()));
    python.stderr.on('data', (data) => (stderr += data.toString()));

    await new Promise((resolve) => python.on('close', resolve));

    if (stderr) {
      console.warn(` Python error: ${stderr}`);
      return;
    }

    const result = JSON.parse(stdout);
    console.log(` Extracted from ${fileName}:`, result);

    const form = new FormData();
    form.append('files', pdfBuffer, {
      filename: fileName,
      contentType: 'application/pdf',
    });
    form.append('college', 'Auto');
    form.append('exam_date', new Date().toISOString());
    form.append('expiry_date', new Date(Date.now() + 7 * 86400000).toISOString());

    form.append('name', result.name);
    form.append('email', result.email);
    form.append('phone', result.phone);
    form.append('education', result.education);
    form.append('experience', result.experience);
    form.append('skills', JSON.stringify(result.skills));
    form.append('projects', JSON.stringify(result.projects));

    const uploadRes = await axios.post(uploadUrl, form, {
      headers: form.getHeaders(),
    });
    if (uploadRes.status === 200) {
      console.log(` Uploaded: ${fileName}`);
    } else {
      console.error(` Upload failed for ${fileName}`);
    }
  } catch (err: any) {
    console.error(` Upload failed for ${fileName}:`);
    if (err.response) {
      console.error(`  → Status: ${err.response.status}`);
      console.error(`  → Body:`, err.response.data);
    } else {
      console.error(err.message || err);
    }
  }
}
async function main() {
  const token = await getGraphToken();
  const { siteId, driveId } = await fetchSiteAndDriveId(token);
  const files = await fetchPdfFiles(siteId, driveId, token);

  console.log(` Found ${files.length} PDF resumes...`);

  for (const file of files) {
    const downloadUrl = file['@microsoft.graph.downloadUrl'];
    await processResume(downloadUrl, file.name);
  }

  console.log(' All resumes processed.');
}

main().catch(console.error);

