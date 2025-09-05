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

def _invite_html(
    *,
    candidate_id: int,
    candidatename: str,
    candidateEmail: str,
    candidateUsername: str,
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
        <p><strong>Username:</strong> <span style="font-weight: bold; color: #2a6cb5;">{candidateUsername}</span></p>
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
        job_id: int,
        top_n: Optional[int] = None,
        send_all: bool = False,
        explicit_recipients: Optional[Dict[str, str]] = None,
        concurrency: Optional[int] = None,  # override at call-site; else ENV or default 6
    ) -> Dict[str, Any]:
        """
        FAST version:
          • One SQL to fetch ALL recipients + extras.
          • Concurrent Gmail sends (bounded).
          • Concurrent audits after sends.

        Returns: {"status","sent","attempted","failures":[...],"details":[...]}
        """
        import json
        import asyncio

        # ---------- config ----------
        # You can tune with env EMAIL_SEND_CONCURRENCY=8
        try:
            default_c = int(os.getenv("EMAIL_SEND_CONCURRENCY", "6"))
        except Exception:
            default_c = 6
        CONC = int(concurrency or default_c)
        CONC = max(1, min(CONC, 16))  # keep it sane

        # ---------- 1) resolve recipients in one shot ----------
        if explicit_recipients:
            rows = [
                {
                    "candidate_name": n.strip(),
                    "email": (e or "").strip(),
                    "exam_url": "",
                    "temp_pwd": "",
                    "temp_user": (e or "").strip(),
                    "exam_dt": None,
                }
                for n, e in explicit_recipients.items()
                if str(n).strip()
            ]
        else:
            lim = "" if send_all else f"LIMIT {int(top_n or 5)}"
            # Use CandidateScore.resume_email (populated at store time) and
            # LEFT JOIN twice to fetch extras by email first, then by name as a fallback.
            q = f"""
                SELECT
                  cs.candidate_name,
                  COALESCE(NULLIF(cs.resume_email,''), r1.email, r2.email, r1.candidate_email, r2.candidate_email, '') AS email,
                  COALESCE(r1.candidate_exam_url, r2.candidate_exam_url, '')      AS exam_url,
                  COALESCE(r1.candidate_temp_password, r2.candidate_temp_password, '') AS temp_pwd,
                  COALESCE(r1.candidate_temp_name, r2.candidate_temp_name, NULL)  AS temp_user,
                  COALESCE(r1.candidate_exam_date, r2.candidate_exam_date, NULL)  AS exam_dt
                FROM public."CandidateScore" cs
                LEFT JOIN public.resumes r1
                  ON NULLIF(cs.resume_email,'') IS NOT NULL
                 AND LOWER(r1.email) = LOWER(cs.resume_email)
                LEFT JOIN public.resumes r2
                  ON NULLIF(cs.resume_email,'') IS NULL
                 AND LOWER(r2.full_name) = LOWER(cs.candidate_name)
                WHERE cs.job_id = %(job_id)s
                ORDER BY cs.final_rank ASC
                {lim}
            """
            r = await self._select(q, params={"job_id": int(job_id)})
            if r.get("status") != "success":
                return {"status": "error", "error": r.get("error") or r}
            rows = r.get("data") or []

        # Separate out missing emails immediately (fast fail)
        attempted = 0
        failures: list[dict] = []
        to_send: list[dict] = []
        for rec in rows:
            name = (rec.get("candidate_name") or "").strip()
            email = (rec.get("email") or "").strip()
            if not email:
                failures.append({"name": name, "email": "", "reason": "missing_email"})
                continue
            attempted += 1
            to_send.append({
                "name": name,
                "email": email,
                "exam_url": rec.get("exam_url") or "",
                "temp_pwd": rec.get("temp_pwd") or "",
                "temp_user": (rec.get("temp_user") or "") or email,
                "exam_dt": rec.get("exam_dt"),
            })

        if not attempted and not explicit_recipients:
            return {"status": "error", "error": "No ranked candidates with emails for this job_id."}

        # ---------- 2) concurrent send ----------
        sem = asyncio.Semaphore(CONC)

        def _looks_ok(res: dict) -> bool:
            try:
                blob = json.dumps(res, ensure_ascii=False).lower()
            except Exception:
                blob = str(res).lower()
            if "invalid_grant" in blob:
                return False
            if "error" in blob and ("invalid" in blob or "failed" in blob or "denied" in blob):
                return False
            status = str(res.get("status", "")).lower()
            return (
                res.get("ok") is True
                or status in {"ok", "success", "sent", "delivered"}
                or any(res.get(k) for k in ("id", "messageId", "threadId"))
            )

        async def _send_one(rec: dict) -> dict:
            async with sem:
                name = rec["name"]
                email = rec["email"]
                html = _invite_html(
                    candidate_id=None,
                    candidatename=name,
                    candidateEmail=email,
                    candidateUsername=rec["temp_user"],
                    candidatetempPassword=rec["temp_pwd"],
                    candidateExam_URL=rec["exam_url"],
                    exam_dt=rec["exam_dt"],
                )
                try:
                    res = await self.gmail.send_email(
                        to=[email],
                        subject="Interview Invitation - JMAN",
                        body="",
                        html=html,
                    )
                except Exception as e:
                    res = {"status": "error", "error": str(e)}
                ok = bool(isinstance(res, dict) and _looks_ok(res))
                return {
                    "name": name, "email": email, "ok": ok, "raw": res,
                    "temp_user": rec["temp_user"], "temp_pwd": rec["temp_pwd"], "exam_url": rec["exam_url"]
                }

        send_results = await asyncio.gather(*[ _send_one(r) for r in to_send ], return_exceptions=False)

        # ---------- 3) build audits & run them concurrently ----------
        audit_payloads = []
        details = []
        sent = 0
        for it in send_results:
            ok = it["ok"]
            details.append({
                "name": it["name"], "email": it["email"], "type": "invite",
                "subject": "Interview Invitation - JMAN",
                "ok": ok, "send_result": it["raw"],
            })
            if not ok:
                reason = it["raw"].get("error") if isinstance(it["raw"], dict) else str(it["raw"])
                failures.append({"name": it["name"], "email": it["email"], "reason": reason, "raw_result": it["raw"]})
            else:
                sent += 1

            audit_payloads.append({
                "job_id": int(job_id),
                "candidate_name": it["name"],
                "candidate_email": it["email"],
                "email_type": "invite",
                "subject": "Interview Invitation - JMAN",
                "username": it["temp_user"],
                "password": it["temp_pwd"],
                "exam_link": it["exam_url"],
                "send_status": "ok" if ok else "error",
                "raw_result": it["raw"],
            })

        # Fire all audits concurrently to minimize round-trips
        async def _audit_one(p):
            try:
                return await self._call_tool("log_email_audit", p)
            except Exception as e:
                return {"status": "error", "error": str(e)}

        await asyncio.gather(*[ _audit_one(p) for p in audit_payloads ], return_exceptions=True)

        # ---------- 4) final status ----------
        status = "success" if attempted and sent == attempted else ("partial" if sent > 0 else "error")
        return {"status": status, "sent": sent, "attempted": attempted, "failures": failures, "details": details}


    
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