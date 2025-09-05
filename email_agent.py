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
    

    async def upsert_exam_credentials(self, records: List[Tuple[str, str, str, str]]) -> Dict[str, Any]:
        """
        records: list of (candidate_email, username, password, exam_link)
        """
        payload = [
            {
                "candidate_email": e,
                "username": u,
                "password": p,
                "exam_link": l,
            } for (e, u, p, l) in (records or [])
        ]
        return await self._call("upsert_exam_credentials", {"records": payload})

    async def log_email_audit(
        self,
        *,
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
    ) -> Dict[str, Any]:
        return await self._call("log_email_audit", {
            "job_id": job_id,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "email_type": email_type,
            "subject": subject,
            "username": username,
            "password": password,
            "exam_link": exam_link,
            "send_status": send_status,
            "raw_result": raw_result,
        })


    async def latest_job_id(self) -> Optional[int]:
        # created_at may not exist; prefer id DESC
        r2 = await self.sql("SELECT id FROM JobDescription ORDER BY id DESC LIMIT 1")
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
        await self.upsert_exam_credentials(records)


    async def ensure_email_audit_table(self) -> None:
        q = """
        CREATE TABLE IF NOT EXISTS EmailAudit (
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
        await self.log_email_audit(
            job_id=job_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            email_type=email_type,
            subject=subject,
            username=username,
            password=password,
            exam_link=exam_link,
            send_status=send_status,
            raw_result=raw_result,
        )


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
        """
        Return a mapping {candidate_name -> email} for the top N candidates of a job.
        - Inspects public."CandidateScore" columns via information_schema (Postgres)
        - Prefers: name col ∈ {candidate_name, name, full_name}
                   rank col ∈ {final_rank, rank, id, created_at}
                   email col ∈ {resume_email}
        """
        # 1) Discover available columns from information_schema (Postgres)
        colq = """
            SELECT LOWER(column_name) AS column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='CandidateScore'
        """
        rcols = await self.sql(colq) if hasattr(self, "sql") else await self._select(colq)
        cols = {row.get("column_name", "") for row in (rcols.get("data") or [])} if rcols.get("status") == "success" else set()

        # 2) Choose best-fit columns
        name_col = "candidate_name" if "candidate_name" in cols else ("name" if "name" in cols else "full_name")
        email_col = "resume_email" if "resume_email" in cols else None
        if "final_rank" in cols:
            rank_col = "final_rank"
        elif "rank" in cols:
            rank_col = "rank"
        elif "id" in cols:
            rank_col = "id"
        elif "created_at" in cols:
            rank_col = "created_at"
        else:
            rank_col = None  # we'll omit ORDER BY in worst case

        order_clause = f'ORDER BY cs."{rank_col}" ASC' if rank_col else ""

        # 3) Build the SELECT (quoted identifier for case-sensitive table name)
        if email_col:
            q = f'''
                SELECT cs."{name_col}" AS candidate_name, cs."{email_col}" AS email
                FROM public."CandidateScore" cs
                WHERE cs.job_id = %(job_id)s AND TRIM(COALESCE(cs."{email_col}", '')) <> ''
                {order_clause}
                LIMIT %(limit)s
            '''
        else:
            q = f'''
                SELECT cs."{name_col}" AS candidate_name,
                       COALESCE(r.email, cs.resume_email, '') AS email
                FROM public."CandidateScore" cs
                LEFT JOIN public.resumes r
                  ON LOWER(r.full_name) = LOWER(cs."{name_col}")
                WHERE cs.job_id = %(job_id)s
                {order_clause}
                LIMIT %(limit)s
            '''

        r = await (self.sql(q) if hasattr(self, "sql") else self._select(q, params={"job_id": job_id, "limit": n}))
        # If self.sql(...) doesn’t accept params, pass literal; if it does, prefer params. If using _select above, we passed params.

        if r.get("status") != "success":
            return {}

        emails: Dict[str, str] = {}
        for row in r.get("data", []):
            nm = (row.get("candidate_name") or "").strip()
            em = (row.get("email") or "").strip()
            if nm and em:
                emails[nm] = em
        return emails


# email_agent.py
# Complete replacement module

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from mcp_client import MCPClient
from gmail_mcp_client import GmailMCPClient


def _invite_html(
    *,
    candidate_id: int,
    candidatename: str,
    candidateEmail: str,
    candidatetempPassword: str,
    candidateExam_URL: str,
    exam_dt: Optional[str],
) -> str:
    """Very simple HTML template for the interview invite."""
    exam_dt_str = (
        datetime.fromisoformat(exam_dt).strftime("%d %b %Y, %I:%M %p")
        if isinstance(exam_dt, str) and exam_dt
        else "TBD"
    )
    return f"""
    <html>
      <body style="font-family: Arial, Helvetica, sans-serif; line-height:1.5;">
        <h2 style="margin-bottom:0">Interview Invitation - JMAN</h2>
        <p>Hi <b>{candidatename}</b>,</p>
        <p>
          You are invited to complete the online assessment for the next step of your interview process.
        </p>
        <table cellpadding="6" cellspacing="0" border="0" style="border:1px solid #ddd;">
          <tr><td><b>Candidate</b></td><td>{candidatename}</td></tr>
          <tr><td><b>Email</b></td><td>{candidateEmail}</td></tr>
          <tr><td><b>Exam Link</b></td><td><a href="{candidateExam_URL}">{candidateExam_URL}</a></td></tr>
          <tr><td><b>Temp Username</b></td><td>{candidateEmail}</td></tr>
          <tr><td><b>Temp Password</b></td><td>{candidatetempPassword}</td></tr>
          <tr><td><b>Exam Date</b></td><td>{exam_dt_str}</td></tr>
          <tr><td><b>Candidate ID</b></td><td>{candidate_id}</td></tr>
        </table>
        <p>
          Please complete the assessment by the scheduled date. If you have any questions,
          reply to this email.
        </p>
        <p>Best,<br/>Recruiting Team</p>
      </body>
    </html>
    """.strip()


class EmailOrchestrator:
    """
    Orchestrates interview-invite emails:
      - Reads recipient + credential info from DB via MCP tool `execute_database_query` (SELECT-only)
      - Sends mail via Gmail MCP client
      - Audits via MCP tool `log_email_audit` (recommended) if available
    """

    def __init__(self, server_script_path: str = "mcp_server.py"):
        # One MCP DB client (correct constructor arg name)
        self.db = MCPClient(server_script_path=server_script_path)
        # One Gmail MCP client for sending
        self.gmail = GmailMCPClient()

    # ---------- Internal MCP helpers ----------

    async def _call_tool(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generic tool caller."""
        return await self.db.call_tool(tool, args)

    async def _select(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        SELECT-only wrapper around server's execute_database_query tool.
        Returns dict with keys: status, data, columns, results_count...
        """
        return await self._call_tool("execute_database_query", {"query": sql, "params": params or {}})

    # ---------- Public API ----------

    async def send_interview_invites(
        self,
        *,
        job_id: Optional[int] = None,
        explicit_recipients: Optional[Dict[str, str]] = None,
        top_n: int = 5,
        send_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends interview invitation emails and audits every attempt.

        Selection:
          - If explicit_recipients is provided, use exactly that mapping {name -> email}
          - Else read top candidates for job_id from CandidateScore ⟷ resumes view.

        Returns:
          {
            "status": "success" | "partial" | "error",
            "sent": <int>,               # number actually sent
            "attempted": <int>,          # recipients iterated
            "failures": [ {name, email, reason, raw_result} ... ],
            "details":  [ {name, email, subject, type, ok} ... ]
          }
        """
        # 1) Determine recipients
        if explicit_recipients:
            recipients = [
                {"candidate_name": name.strip(), "email": (email or "").strip()}
                for name, email in explicit_recipients.items()
            ]
        else:
            if not job_id:
                # Last ranked job is auto-detected elsewhere; return a clear error here
                return {"status": "error", "error": "No job_id to pick recipients from."}

            limit_clause = "" if send_all else f"LIMIT {int(top_n or 5)}"
            query = f"""
                SELECT
                    cs.candidate_name,
                    COALESCE(r.email, cs.resume_email, '') AS email
                FROM public."CandidateScore" cs
                LEFT JOIN public.resumes r
                  ON LOWER(r.full_name) = LOWER(cs.candidate_name)
                WHERE cs.job_id = %(job_id)s
                ORDER BY cs.final_rank ASC
                {limit_clause}
            """
            r = await self._select(query, params={"job_id": int(job_id)})
            if r.get("status") != "success" or not r.get("data"):
                return {"status": "error", "error": "No ranked candidates found for the given job_id."}
            recipients = r["data"]

        sent = 0
        attempted = 0
        details: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []

        # 2) Iterate recipients
        for rec in recipients:
            name = (rec.get("candidate_name") or "").strip()
            email = (rec.get("email") or "").strip()
            if not email:
                failures.append({"name": name, "email": "", "reason": "missing_email"})
                # Audit as error with minimal context
                try:
                    await self._call_tool("log_email_audit", {
                        "job_id": int(job_id) if job_id else None,
                        "candidate_name": name,
                        "candidate_email": "",
                        "email_type": "invite",
                        "subject": "Interview Invitation - JMAN",
                        "username": None,
                        "password": None,
                        "exam_link": None,
                        "send_status": "error",
                        "raw_result": {"error": "missing_email"}
                    })
                except Exception:
                    pass
                continue

            attempted += 1

            # 2a) Per-candidate extras from resumes view
            r2 = await self._select(
                """
                SELECT
                    COALESCE(candidate_exam_url, '')       AS candidate_exam_url,
                    COALESCE(candidate_temp_password, '')  AS candidate_temp_password,
                    COALESCE(candidate_temp_name, '')      AS candidate_temp_name,
                    candidate_exam_date,
                    candidate_expiry,
                    COALESCE(candidate_id, 0)              AS candidate_id
                FROM public.resumes
                WHERE LOWER(full_name) = LOWER(%(full_name)s)
                LIMIT 1
                """,
                params={"full_name": name},
            )
            row = (r2.get("data") or [{}])[0] if r2.get("status") == "success" and r2.get("data") else {}
            exam_url = row.get("candidate_exam_url", "") or ""
            temp_pwd = row.get("candidate_temp_password", "") or ""
            temp_user = row.get("candidate_temp_name") or email
            exam_date = row.get("candidate_exam_date")
            candidate_id = int(row.get("candidate_id") or 0)

            # 2b) Render HTML
            html = _invite_html(
                candidate_id=candidate_id,
                candidatename=name,
                candidateEmail=email,
                candidatetempPassword=temp_pwd,
                candidateExam_URL=exam_url,
                exam_dt=exam_date,
            )

            # 2c) Send email via Gmail MCP
            try:
                send_result = await self.gmail.send_email(
                    to=[email],
                    subject="Interview Invitation - JMAN",
                    body="",  # keep plain body empty; we send HTML
                    html=html,
                )
            except Exception as e:
                send_result = {"status": "error", "error": str(e)}

            # Robust success detection across servers
            ok = False
            if isinstance(send_result, dict):
                status = str(send_result.get("status", "")).lower()
                ok = (
                    send_result.get("ok") is True
                    or status in {"ok", "success", "sent"}
                    or any(send_result.get(k) for k in ("id", "messageId", "threadId"))
                )

            # 2d) Audit
            send_status = "ok" if ok else "error"
            try:
                await self._call_tool("log_email_audit", {
                    "job_id": int(job_id) if job_id else None,
                    "candidate_name": name,
                    "candidate_email": email,
                    "email_type": "invite",
                    "subject": "Interview Invitation - JMAN",
                    "username": temp_user,
                    "password": temp_pwd,
                    "exam_link": exam_url,
                    "send_status": send_status,
                    "raw_result": send_result,
                })
            except Exception:
                # Non-fatal: continue even if audit fails
                pass

            details.append({
                "name": name,
                "email": email,
                "type": "invite",
                "subject": "Interview Invitation - JMAN",
                "ok": bool(ok),
                "send_result": send_result,
            })

            if ok:
                sent += 1
            else:
                reason = send_result.get("error") or send_result.get("message") or send_result
                failures.append({"name": name, "email": email, "reason": str(reason), "raw_result": send_result})

        status = "success" if sent == attempted and attempted > 0 else ("partial" if sent > 0 else "error")
        return {
            "status": status,
            "sent": sent,
            "attempted": attempted,
            "failures": failures,
            "details": details,
        }

    
    async def act_on_instruction(
        self,
        text: str,
        *,
        job_id_override: Optional[int] = None,
        explicit_recipients: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Understands:
          - "send email(s) to everyone under job_id:6"
          - "send mails to top 3 in job 6"
          - "email top 2 for job_id 6"
          - "send all invites for job 7"
        Falls back to the latest job_id if none provided and override is missing.
        """
        import re

        t = (text or "").lower()

        # Everyone?
        send_all = bool(re.search(r"\b(everyone|all|send all|all candidates)\b", t))

        # top N?
        m = re.search(r"\b(?:top|first|send|invite)\s+(\d+)\b", t)
        top_n = int(m.group(1)) if m else None

        # job id?
        jm = re.search(r"\bjob(?:_?id)?\s*[:=]?\s*(\d+)\b", t) or re.search(r"\bjob\s+(\d+)\b", t)
        job_id = int(jm.group(1)) if jm else None
        if job_id is None and job_id_override is not None:
            job_id = int(job_id_override)

        # Fall back to newest job_id
        if job_id is None:
            r = await self._select('SELECT id FROM public."JobDescription" ORDER BY id DESC LIMIT 1')
            if r.get("status") == "success" and r.get("data"):
                job_id = int(r["data"][0]["id"])

        if job_id is None:
            return {"status": "error", "error": "No job_id found (nothing ranked yet, or not specified)."}

        # Delegate
        result = await self.send_interview_invites(
            job_id=job_id,
            top_n=top_n,
            send_all=bool(send_all),
            explicit_recipients=explicit_recipients,
        )

        # Normalize response
        if result.get("status") not in {"success", "partial"}:
            return {"status": "error", "error": result.get("error") or result, "job_id": job_id}

        result["job_id"] = job_id
        return result

    
    
# --------- Convenience wrapper for quick calls from scripts ----------

async def send_interview_invites(
    self,
    *,
    job_id: int,
    top_n: Optional[int] = None,
    send_all: bool = False,
    explicit_recipients: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Sends interview emails and audits each attempt.
    Selection:
      - explicit_recipients: {name -> email}
      - else: read from CandidateScore for the given job_id
              (top_n unless send_all=True)

    Returns: status, sent, attempted, failures[], details[]
    """
    # 1) Resolve recipients
    if explicit_recipients:
        recipients = [
            {"candidate_name": n.strip(), "email": (e or "").strip()}
            for n, e in explicit_recipients.items()
            if str(n).strip()
        ]
    else:
        lim = "" if send_all else f"LIMIT {int(top_n or 5)}"
        # We now trust CandidateScore.resume_email (populated at store time),
        # but still left-join resumes for a fallback.
        q = f"""
            SELECT
              cs.candidate_name,
              COALESCE(NULLIF(cs.resume_email,''), r.email, r.candidate_email, '') AS email
            FROM public."CandidateScore" cs
            LEFT JOIN public.resumes r
              ON LOWER(r.full_name) = LOWER(cs.candidate_name)
            WHERE cs.job_id = %(job_id)s
            ORDER BY cs.final_rank ASC
            {lim}
        """
        r = await self._select(q, params={"job_id": int(job_id)})
        if r.get("status") != "success":
            return {"status": "error", "error": r.get("error") or r}
        recipients = r.get("data") or []

    sent = 0
    attempted = 0
    details: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    # 2) Per recipient
    for rec in recipients:
        name = (rec.get("candidate_name") or "").strip()
        email = (rec.get("email") or "").strip()
        if not email:
            failures.append({"name": name, "email": "", "reason": "missing_email"})
            # Audit as failure
            try:
                await self._call_tool("log_email_audit", {
                    "job_id": int(job_id),
                    "candidate_name": name,
                    "candidate_email": "",
                    "email_type": "invite",
                    "subject": "Interview Invitation - JMAN",
                    "username": None,
                    "password": None,
                    "exam_link": None,
                    "send_status": "error",
                    "raw_result": {"error": "missing_email"},
                })
            except Exception:
                pass
            continue

        attempted += 1

        # Fetch extras from resumes (credentials / link)
        extras = await self._select(
            """
            SELECT
              COALESCE(candidate_exam_url,'')      AS exam_url,
              COALESCE(candidate_temp_password,'') AS temp_pwd,
              COALESCE(candidate_temp_name,'')     AS temp_user,
              candidate_exam_date
            FROM public.resumes
            WHERE LOWER(email) = LOWER(%(email)s) OR LOWER(full_name) = LOWER(%(name)s)
            LIMIT 1
            """,
            params={"email": email, "name": name},
        )
        row = (extras.get("data") or [{}])[0] if extras.get("status") == "success" else {}
        exam_url = row.get("exam_url", "") or ""
        temp_pwd = row.get("temp_pwd", "") or ""
        temp_user = (row.get("temp_user") or "") or email
        exam_dt = row.get("candidate_exam_date")

        html = _invite_html(
            candidate_id=None,
            candidatename=name,
            candidateEmail=email,
            candidatetempPassword=temp_pwd,
            candidateExam_URL=exam_url,
            exam_dt=exam_dt,
        )

        try:
            send_result = await self.gmail.send_email(
                to=[email],
                subject="Interview Invitation - JMAN",
                body="",
                html=html,
            )
        except Exception as e:
            send_result = {"status": "error", "error": str(e)}

        ok = False
        if isinstance(send_result, dict):
            status = str(send_result.get("status", "")).lower()
            ok = (
                send_result.get("ok") is True
                or status in {"ok", "success", "sent"}
                or any(send_result.get(k) for k in ("id", "messageId", "threadId"))
            )

        send_status = "ok" if ok else "error"

        # Audit
        try:
            await self._call_tool("log_email_audit", {
                "job_id": int(job_id),
                "candidate_name": name,
                "candidate_email": email,
                "email_type": "invite",
                "subject": "Interview Invitation - JMAN",
                "username": temp_user,
                "password": temp_pwd,
                "exam_link": exam_url,
                "send_status": send_status,
                "raw_result": send_result,
            })
        except Exception:
            pass

        details.append({
            "name": name, "email": email, "type": "invite",
            "subject": "Interview Invitation - JMAN",
            "ok": bool(ok), "send_result": send_result,
        })

        if ok:
            sent += 1
        else:
            failures.append({
                "name": name, "email": email,
                "reason": send_result.get("error") or send_result.get("message") or send_result,
                "raw_result": send_result,
            })

    status = "success" if attempted and sent == attempted else ("partial" if sent > 0 else "error")
    return {"status": status, "sent": sent, "attempted": attempted, "failures": failures, "details": details}

