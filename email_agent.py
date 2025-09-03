from __future__ import annotations

import json
import logging
import os
import re, asyncio
import secrets
import string
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_client import MCPClient 
from gmail_mcp_client import GmailMCPClient
from mcp_tools import DatabaseManager

logger = logging.getLogger(__name__)

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://careers.example.com")

def _fmt_exam_dt(val: Any) -> str:
    if not val:
        return "TBD"
    # mcp returns ISO strings usually; try to pretty print
    try:
        if isinstance(val, str):
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        else:
            dt = val
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(val)


def _invite_html(candidate_id: int,
                 candidatename: str,
                 candidateEmail: str,
                 candidatetempPassword: Optional[str],
                 candidateExam_URL: Optional[str],
                 exam_dt: Any) -> str:
    formattedExamDate = _fmt_exam_dt(exam_dt)
    accept_url  = f"{APP_BASE_URL}/{candidate_id}/accept"
    decline_url = f"{APP_BASE_URL}/{candidate_id}/decline"

    return f"""
      <p>Dear {candidatename},</p>

      <p>Greetings from JMAN Group!</p>

      <p>We would like to block your calendar for the <strong>Level 1 Technical Interview</strong>. Kindly ensure your availability for the session. Please find your interview details below:</p>

      <h4>Interview Details</h4>
      <div style="margin-left: 20px;">
        <p><strong>Date and Time:</strong> {formattedExamDate}</p>
        <p><strong>Position:</strong> Software Engineer</p>
      </div>

      <h4>Login Credentials</h4>
      <div style="margin-left: 20px;">
        <p><strong>Username:</strong> <span style="font-weight: bold; color: #2a6cb5;">{candidateEmail}</span></p>
        <p><strong>Password:</strong> <span style="font-weight: bold; color: #2a6cb5;">{candidatetempPassword or "—"}</span></p>
      </div>

      <p>Use the link below to log in and access your interview details:</p>
      <p><a href="{candidateExam_URL or APP_BASE_URL}" style="color: #2a6cb5; text-decoration: underline;">Interview Link</a></p>

      <p>We kindly request you to confirm your attendance by selecting one of the options below:</p>

      <div style="margin: 20px 0;">
        <a href="{accept_url}"
          style="color: #4CAF50; font-weight: bold; text-decoration: none; font-size: 16px; margin-right: 30px; display: inline-block;">
          ✔ Accept Invitation
        </a>
        <a href="{decline_url}"
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
      <p>JMAN Group</p>
    """


class ResumeDBClient:
    def __init__(self, server_script_path: str = "mcp_server.py") -> None:
        self.server_params = StdioServerParameters(command="python", args=[server_script_path])

    async def _call(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as sess:
                    await sess.initialize()
                    res = await sess.call_tool(tool, args or {})
                    if hasattr(res, "content") and res.content:
                        item = res.content[0]
                        text = getattr(item, "text", str(item))
                        try:
                            return json.loads(text)
                        except Exception:
                            return {"status": "success", "result": text}
                    return {"status": "success", "result": str(res)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def sql(self, query: str) -> Dict[str, Any]:
        return await self._call("execute_database_query", {"query": query})

    async def latest_job_id(self) -> Optional[int]:
        # created_at may not exist; prefer id DESC
        r2 = await self.sql("SELECT id FROM jobdescription ORDER BY id DESC LIMIT 1")
        if r2.get("status") == "success" and r2.get("data"):
            return r2["data"][0]["id"]
        return None

    async def ensure_credentials_table(self) -> None:
        q = """
        CREATE TABLE IF NOT EXISTS exam_credentials (
            candidate_email TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            exam_link TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await self.sql(q)

    async def upsert_credentials(self, records: List[Tuple[str, str, str, str]]) -> None:
        if not records:
            return
        values = ", ".join([f"( '{e}', '{u}', '{p}', '{l}' )" for (e, u, p, l) in records])
        q = f"""
        INSERT INTO exam_credentials (candidate_email, username, password, exam_link)
        VALUES {values}
        ON CONFLICT(candidate_email) DO UPDATE SET
            username=excluded.username,
            password=excluded.password,
            exam_link=excluded.exam_link,
            created_at=CURRENT_TIMESTAMP
        """
        await self.sql(q)

    async def ensure_email_audit_table(self) -> None:
        q = """
        CREATE TABLE IF NOT EXISTS email_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            job_id INTEGER,
            candidate_name TEXT,
            candidate_email TEXT,
            email_type TEXT,            -- 'congrats' | 'rejection'
            subject TEXT,
            username TEXT,
            password TEXT,
            exam_link TEXT,
            send_status TEXT,           -- 'ok' | 'error'
            raw_result TEXT
        )
        """
        await self.sql(q)

    async def insert_email_audit(
        self,
        job_id: Optional[int],
        candidate_name: str,
        candidate_email: str,
        email_type: str,
        subject: str,
        username: Optional[str],
        password: Optional[str],
        exam_link: Optional[str],
        send_status: str,
        raw_result: Dict[str, Any],
    ) -> None:
        subj = subject.replace("'", "''")
        name = (candidate_name or "").replace("'", "''")
        email = (candidate_email or "").replace("'", "''")
        et = email_type.replace("'", "''")
        user = (username or "").replace("'", "''")
        pwd = (password or "").replace("'", "''")
        link = (exam_link or "").replace("'", "''")
        raw = json.dumps(raw_result, ensure_ascii=False).replace("'", "''")
        jid = "NULL" if job_id is None else str(job_id)
        q = f"""
        INSERT INTO email_audit
            (job_id, candidate_name, candidate_email, email_type, subject, username, password, exam_link, send_status, raw_result)
        VALUES
            ({jid}, '{name}', '{email}', '{et}', '{subj}', '{user}', '{pwd}', '{link}', '{send_status}', '{raw}')
        """
        await self.sql(q)

    async def emails_for_names(self, names: List[str]) -> Dict[str, str]:
        if not names:
            return {}
        lowered = [n.lower().replace("'", "''") for n in names]
        in_list = ",".join(f"'{v}'" for v in lowered)
        q = f"""
        SELECT full_name, email FROM resumes
        WHERE email IS NOT NULL AND LOWER(full_name) IN ({in_list})
        """
        r = await self.sql(q)
        emails: Dict[str, str] = {}
        if r.get("status") == "success":
            for row in r.get("data", []):
                emails[row["full_name"]] = row["email"]
        return emails

    async def top_recipients_for_job(self, job_id: int, n: int) -> Dict[str, str]:
        # Use resume_email if present; else join to resumes
        rcols = await self.sql("PRAGMA table_info(candidate_scores)")
        cols = {row.get("name", "").lower() for row in rcols.get("data", [])} if rcols.get("status") == "success" else set()
        name_col = "candidate_name" if "candidate_name" in cols else ("name" if "name" in cols else "full_name")
        rank_col = "final_rank" if "final_rank" in cols else ("rank" if "rank" in cols else None)
        email_col = "resume_email" if "resume_email" in cols else None

        order_clause = f"ORDER BY cs.{rank_col} ASC" if rank_col else "ORDER BY cs.rowid ASC"

        if email_col:
            q = f"""
            SELECT cs.{name_col} AS candidate_name, cs.{email_col} AS email
            FROM candidate_scores cs
            WHERE cs.job_id = {job_id} AND TRIM(COALESCE(cs.{email_col}, '')) <> ''
            {order_clause}
            LIMIT {n}
            """
        else:
            q = f"""
            SELECT cs.{name_col} AS candidate_name, COALESCE(r.email, '') AS email
            FROM candidate_scores cs
            LEFT JOIN resumes r ON LOWER(r.full_name) = LOWER(cs.{name_col})
            WHERE cs.job_id = {job_id}
            {order_clause}
            LIMIT {n}
            """
        r = await self.sql(q)
        out: Dict[str, str] = {}
        if r.get("status") == "success":
            for row in r.get("data", []):
                nm = (row.get("candidate_name") or "").strip()
                em = (row.get("email") or "").strip()
                if nm and em:
                    out[nm] = em
        return out

class EmailOrchestrator:
    """
    Uses MCP server's `execute_database_query` for all DB reads/writes.
    No direct psycopg/sqlite connections here.
    """
    def __init__(self, server_script: str = "mcp_server.py"):
        self.server_script = server_script
        self.gmail = GmailMCPClient()
        
        async def _mcp(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
            client = MCPClient(server_cmd=["python", self.server_script])
            return await client.call_tool(tool, args)

        async def send_interview_invites(self, job_id: int,
                                 top_n: Optional[int] = None,
                                 send_all: bool = False,
                                 explicit_recipients: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
            """
            Sends 'Interview Invitation - JMAN' using fields from public.resumes:
              candidate_exam_url, candidate_temp_password, candidate_temp_name, candidate_exam_date, candidate_expiry.
            If explicit_recipients provided (name->email), it uses exactly those.
            Else derives from candidate_scores for job_id (top_n or all).
            Audits to email_audit via MCP.
            """
            # 1) Who to send
            if explicit_recipients:
                rows = [{"candidate_name": n, "email": e} for n, e in explicit_recipients.items()]
            else:
                limit_clause = "" if send_all else f"LIMIT {int(top_n or 5)}"
                r = await self.mcp.sql(f"""
                    SELECT cs.candidate_name, COALESCE(r.email, cs.resume_email, '') AS email
                    FROM public.candidate_scores cs
                    LEFT JOIN public.resumes r ON LOWER(r.full_name) = LOWER(cs.candidate_name)
                    WHERE cs.job_id = {int(job_id)}
                    ORDER BY cs.final_rank ASC
                    {limit_clause}
                """)
                if r.get("status") != "success" or not r.get("data"):
                    return {"status":"error","error":"No ranked candidates found"}
                rows = r["data"]

            sent = 0
            out = []
            for rec in rows:
                name = rec.get("candidate_name") or ""
                email = (rec.get("email") or "").strip()
                if not email: continue

                # 2) Fetch per-candidate creds from the resumes view
                r2 = await self.mcp.sql(f"""
                    SELECT candidate_exam_url, candidate_temp_password, candidate_temp_name, candidate_exam_date, candidate_expiry
                    FROM public.resumes
                    WHERE LOWER(full_name) = LOWER('{name.replace("'", "''")}')
                    LIMIT 1
                """)
                row = (r2.get("data") or [{}])[0] if r2.get("status") == "success" else {}
                exam_url = row.get("candidate_exam_url") or ""
                temp_pwd = row.get("candidate_temp_password") or ""
                temp_user = row.get("candidate_temp_name") or email
                exam_date = row.get("candidate_exam_date")

                html = _invite_html(
                    candidate_id=0,  # if you have an id in view, use it here
                    candidatename=name,
                    candidateEmail=email,
                    candidatetempPassword=temp_pwd,
                    candidateExam_URL=exam_url,
                    exam_dt=exam_date,
                )
                result = self.gmail.send_email(to=email, subject="Interview Invitation - JMAN", html=html)
                ok = (isinstance(result, dict) and result.get("ok", True))
                status = "ok" if ok else "error"

                # 3) Audit via MCP
                await self.mcp.sql(f"""
                    INSERT INTO public.email_audit
                      (job_id, candidate_name, candidate_email, email_type, subject, username, password, exam_link, send_status, raw_result)
                    VALUES
                      ({int(job_id)}, '{name.replace("'", "''")}', '{email.replace("'", "''")}',
                       'invite', 'Interview Invitation - JMAN',
                       '{temp_user.replace("'", "''")}', '{temp_pwd.replace("'", "''")}', '{(exam_url or "").replace("'", "''")}',
                       '{status}', '{json.dumps(result).replace("'", "''")}')
                """)

                sent += 1
                out.append({"name": name, "to": email})

            return {"status":"success","sent":sent,"recipients":out}


    def send_interview_invites(job_id: int, top_n: Optional[int] = None, send_all: bool = False) -> Dict[str, Any]:
        return asyncio.run(EmailOrchestrator().send_interview_invites(job_id, top_n, send_all))

    