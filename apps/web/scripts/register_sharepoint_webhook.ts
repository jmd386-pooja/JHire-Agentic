import axios from 'axios';
import * as dotenv from 'dotenv';
dotenv.config();

const tenantId = process.env.AZURE_TENANT_ID!;
const clientId = process.env.AZURE_CLIENT_ID!;
const clientSecret = process.env.AZURE_CLIENT_SECRET!;
const resumeFolderId = process.env.RESUME_FOLDER_ID!;
const notificationUrl = process.env.WEBHOOK_NOTIFICATION_URL!; // e.g., https://yourdomain.com/api/sharepoint-listener

async function getGraphToken() {
  const res = await axios.post(
    `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
    new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      scope: 'https://graph.microsoft.com/.default',
      grant_type: 'client_credentials',
    }),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  return res.data.access_token;
}

async function registerWebhook() {
  const token = await getGraphToken();
  const driveId = process.env.SHAREPOINT_DRIVE_ID!; // You should save this after one-time fetch

  const response = await axios.post(
    `https://graph.microsoft.com/v1.0/subscriptions`,
    {
      changeType: 'created',
      notificationUrl,
      resource: `/drives/${driveId}/items/${resumeFolderId}/children`,
      expirationDateTime: new Date(Date.now() + 2.5 * 24 * 60 * 60 * 1000).toISOString(), // 2.5 days
      clientState: 'jhire-secret',
    },
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );

  console.log(' Webhook registered:', response.data);
}

registerWebhook().catch(console.error);
