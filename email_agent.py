from __future__ import annotations

import json
import logging
import os
import re
import secrets
import string
from typing import Dict, Any, List, Optional, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from gmail_mcp_client import GmailMCPClient

logger = logging.getLogger(__name__)


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


def gen_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class EmailOrchestrator:
    def __init__(self, resume_server_script: str = "mcp_server.py") -> None:
        self.db = ResumeDBClient(resume_server_script)
        self.gmail = GmailMCPClient()
        self.exam_base_url = os.getenv("EXAM_BASE_URL", "https://assess.acme.com/start")

    # ---------- Recipients ----------
    async def recipients_from_instruction(self, instruction: str, job_id_override: Optional[int] = None) -> Dict[str, str]:
        inst = instruction.lower()
        names: List[str] = []

        # explicit names after "to ..."
        m = re.search(r"to\s+(.+)$", instruction, re.IGNORECASE)
        if m and all(kw not in inst for kw in ["top", "first", "everyone", "all"]):
            raw = m.group(1)
            parts = [p.strip().strip('"\'' ) for p in raw.split(",")]
            cleaned = []
            for p in parts:
                if not p:
                    continue
                p = re.split(r"\b(with|using|and)\b", p)[0].strip()
                if p:
                    cleaned.append(p)
            names = cleaned

        if "top" in inst or "first" in inst:
            m = re.search(r"(?:top|first)\s+(\d+)", inst)
            n = int(m.group(1)) if m else 5
            job_id = job_id_override or await self.db.latest_job_id()
            if job_id is None:
                return {}
            return await self.db.top_recipients_for_job(job_id, n)

        if "everyone" in inst or "all" in inst:
            r = await self.db.sql("SELECT full_name, email FROM resumes WHERE email IS NOT NULL")
            out: Dict[str, str] = {}
            if r.get("status") == "success":
                for row in r.get("data", []):
                    if row.get("full_name") and row.get("email"):
                        out[row["full_name"]] = row["email"]
            return out

        if names:
            return await self.db.emails_for_names(names)

        return {}

    # ---------- Branding + HTML ----------
    def _brand(self):
        company = os.getenv("COMPANY_NAME", "Hiring Team")
        color = os.getenv("PRIMARY_COLOR", "#1a73e8")
        logo = os.getenv("COMPANY_LOGO_URL", "")
        return company, color, logo

    def _wrap_html(self, title: str, body_html: str) -> str:
        company, color, logo = self._brand()
        logo_html = f'<img src="{logo}" alt="{company}" style="height:40px;margin-bottom:12px;" />' if logo else ""
        return f"""
        <div style="font-family:Arial,Helvetica,sans-serif;line-height:1.55;color:#222;">
          {logo_html}
          <h2 style="color:{color};margin:0 0 12px 0;">{title}</h2>
          <div style="padding:12px 0;">{body_html}</div>
          <div style="margin-top:20px;font-size:12px;color:#666;">This message was sent by {company}.</div>
        </div>
        """

    def build_congrats(self, full_name: str, username: Optional[str], password: Optional[str], link: Optional[str]) -> Tuple[str, str, str]:
        company, _, _ = self._brand()
        subject = f"Congratulations — Next Step with {company}"
        if username and password and link:
            text = f"""Hi {full_name},

Congratulations! You're selected for the next step.

Login details:
  • Username: {username}
  • Password: {password}
  • Exam link: {link}

Please complete the assessment within 48 hours.

Best,
{company}"""
            html_body = f"""
            <p>Hi {full_name},</p>
            <p>Congratulations! You're selected for the next step.</p>
            <ul>
              <li><b>Username:</b> {username}</li>
              <li><b>Password:</b> {password}</li>
              <li><b>Exam link:</b> <a href="{link}">{link}</a></li>
            </ul>
            <p>Please complete the assessment within 48 hours.</p>
            <p>Best,<br/>{company}</p>
            """
        else:
            text = f"""Hi {full_name},

Congratulations! You're selected for the next step.
We'll follow up shortly with your assessment details.

Best,
{company}"""
            html_body = f"""
            <p>Hi {full_name},</p>
            <p>Congratulations! You're selected for the next step.</p>
            <p>We'll follow up shortly with your assessment details.</p>
            <p>Best,<br/>{company}</p>
            """
        html = self._wrap_html("Congratulations", html_body)
        return subject, text, html

    def build_rejection(self, full_name: str) -> Tuple[str, str, str]:
        company, _, _ = self._brand()
        subject = f"Update on Your Application — {company}"
        text = f"""Hi {full_name},

Thank you for your interest. After careful review, we will not be moving forward at this time.

Best,
{company}"""
        html_body = f"""
        <p>Hi {full_name},</p>
        <p>Thank you for your interest. After careful review, we will not be moving forward at this time.</p>
        <p>Best,<br/>{company}</p>
        """
        html = self._wrap_html("Application Update", html_body)
        return subject, text, html

    async def maybe_generate_credentials(self, instruction: str, recipients: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        needs_creds = any(k in instruction.lower() for k in ["username", "password", "exam", "link"])
        if not needs_creds or not recipients:
            return {}

        await self.db.ensure_credentials_table()
        creds_map: Dict[str, Dict[str, str]] = {}
        records: List[Tuple[str, str, str, str]] = []
        for full_name, email in recipients.items():
            username = email.split("@")[0]
            password = gen_password(10)
            token = secrets.token_urlsafe(10)
            link = f"{self.exam_base_url}?token={token}"
            creds_map[full_name] = {"username": username, "password": password, "link": link, "email": email}
            records.append((email, username, password, link))

        await self.db.upsert_credentials(records)
        return creds_map

    async def act_on_instruction(
        self,
        instruction: str,
        *,
        job_id_override: Optional[int] = None,
        explicit_recipients: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        If explicit_recipients is provided (name->email), use that list directly.
        Otherwise derive recipients from instruction (top/first N / everyone / explicit names).
        """
        instruction_l = instruction.lower()

        # Prep audit table
        await self.db.ensure_email_audit_table()

        # Resolve recipients
        if explicit_recipients:
            recipients = {k: v for k, v in explicit_recipients.items() if v}
        else:
            recipients = await self.recipients_from_instruction(instruction, job_id_override=job_id_override)

        if not recipients:
            return {"status": "error", "error": "No recipients resolved from instruction."}

        # Credentials if requested
        creds_map = await self.maybe_generate_credentials(instruction, recipients)

        # Build & send
        results = []
        email_type = "rejection" if ("reject" in instruction_l or "rejection" in instruction_l) else "congrats"

        for full_name, email in recipients.items():
            creds = creds_map.get(full_name, {})
            if email_type == "rejection":
                subj, text, html = self.build_rejection(full_name)
            else:
                subj, text, html = self.build_congrats(full_name, creds.get("username"), creds.get("password"), creds.get("link"))

            r = await self.gmail.send_email([email], subj, text, html=html)
            status = "ok" if (isinstance(r, dict) and r.get("status") != "error") else "error"

            # Audit
            await self.db.insert_email_audit(
                job_id=job_id_override,
                candidate_name=full_name,
                candidate_email=email,
                email_type=email_type,
                subject=subj,
                username=creds.get("username"),
                password=creds.get("password"),
                exam_link=creds.get("link"),
                send_status=status,
                raw_result=r if isinstance(r, dict) else {"raw": str(r)},
            )

            results.append({"name": full_name, "email": email, "subject": subj, "type": email_type, "result": r})

        return {"status": "success", "sent": len(results), "details": results}
