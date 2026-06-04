"""
Enterprise AI Automation Assistant
Fixed Flask application — robust Gemini integration with full fallback support.

Fixes applied:
1. Switched from `google-generativeai` to `google-genai` (correct SDK for genai.Client API)
2. Uses `gemini-1.5-flash` — stable, free-tier friendly model
3. Single combined Gemini call per request (reduces quota usage by 3x)
4. Full fallback system — app never crashes on 429 / quota / rate limit errors
5. Intelligent enterprise mock responses derived from user input keywords
6. Comprehensive exception handling and structured logging
7. Graceful degradation: Gemini failure → fallback, not HTTP 500
"""

import os
import json
import logging
import smtplib
import requests as http_requests
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from database import init_db, save_workflow, get_all_workflows, get_stats, log_activity

load_dotenv()
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

MODEL = "gemini-1.5-flash"

gemini_client = None
gemini_available = False

if GEMINI_API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        gemini_available = True
        logger.info("Gemini client initialized successfully (model: %s)", MODEL)
    except ImportError as e:
        logger.warning("google-genai package not installed: %s — running in fallback mode", e)
    except Exception as e:
        logger.warning("Gemini client init failed: %s — running in fallback mode", e)
else:
    logger.warning("GEMINI_API_KEY not set — running in fallback mode")

init_db()


def is_quota_error(exc: Exception) -> bool:
    """Return True for 429 / quota / rate-limit errors."""
    msg = str(exc).lower()
    return any(k in msg for k in (
        "429", "resource_exhausted", "quota", "rate limit",
        "rate_limit", "too many requests", "exhausted",
    ))


def is_model_error(exc: Exception) -> bool:
    """Return True when the model name is invalid or unavailable."""
    msg = str(exc).lower()
    return any(k in msg for k in (
        "model not found", "invalid model", "not found",
        "404", "unsupported", "deprecated",
    ))


def ai_generate_combined(user_input: str) -> dict | None:
    """
    Single Gemini call that returns summary + tasks + email in one shot.
    Returns None on any failure so the caller can use fallback.
    """
    if not gemini_available or not gemini_client:
        return None

    prompt = f"""You are an enterprise AI automation analyst and project manager.
A user submitted this workflow request:

\"\"\"{user_input}\"\"\"

Return a single valid JSON object with exactly these three keys:

1. "summary" — A professional workflow analysis in 4-5 bullet points (each starting with "•").
   Focus on objectives, key automation opportunities, and expected outcomes.

2. "tasks" — A JSON array of 4 recommended tasks. Each task must have:
   - "title": short task name (max 8 words)
   - "description": one sentence
   - "priority": one of "High", "Medium", or "Low"
   - "department": one of "Engineering", "Operations", "Management", "Marketing", "Finance"
   - "status": always "Pending"

3. "email" — A formal follow-up email. Include a line starting with "Subject:" then the full body.
   Professional tone, signed off as "Enterprise AI Automation Assistant".
   Mention it was AI-generated.

Return ONLY the JSON object. No markdown fences, no extra text."""

    try:
        logger.info("Calling Gemini API (model: %s)", MODEL)
        response = gemini_client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        text = response.text.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end])

        data = json.loads(text)
        logger.info("Gemini response received and parsed successfully")
        return data

    except Exception as exc:
        if is_quota_error(exc):
            logger.warning("Gemini quota/rate-limit hit: %s — switching to fallback", exc)
        elif is_model_error(exc):
            logger.warning("Gemini model error (%s): %s — switching to fallback", MODEL, exc)
        else:
            logger.error("Gemini call failed: %s — switching to fallback", exc)
        return None


def build_fallback_response(user_input: str) -> dict:
    """
    Construct an intelligent enterprise fallback response derived from the
    user's input. Detects domain keywords to produce relevant content.
    This is returned whenever Gemini is unavailable or quota is exhausted.
    """
    text = user_input.lower()
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    if any(k in text for k in ("marketing", "campaign", "brand", "social", "advertis")):
        domain = "Marketing Automation"
        tasks = [
            {"title": "Define campaign objectives and KPIs", "description": "Establish measurable goals and key performance indicators for the campaign.", "priority": "High", "department": "Marketing", "status": "Pending"},
            {"title": "Segment target audience", "description": "Identify and segment the target audience for personalised outreach.", "priority": "High", "department": "Marketing", "status": "Pending"},
            {"title": "Design automated content pipeline", "description": "Build automated content scheduling and distribution workflows.", "priority": "Medium", "department": "Engineering", "status": "Pending"},
            {"title": "Set up analytics tracking", "description": "Configure conversion tracking and campaign analytics dashboards.", "priority": "Medium", "department": "Operations", "status": "Pending"},
        ]
        bullets = [
            "• Automate multi-channel marketing campaign execution to reduce manual overhead",
            "• Implement audience segmentation logic for personalised content delivery",
            "• Integrate analytics pipeline for real-time campaign performance monitoring",
            "• Deploy A/B testing framework to optimise engagement and conversion rates",
            "• Schedule post-campaign reporting automation for stakeholder visibility",
        ]
    elif any(k in text for k in ("finance", "payment", "invoice", "budget", "accounting", "cost")):
        domain = "Finance Process Automation"
        tasks = [
            {"title": "Audit existing financial workflows", "description": "Review and document current manual financial processes for automation candidates.", "priority": "High", "department": "Finance", "status": "Pending"},
            {"title": "Implement invoice processing automation", "description": "Deploy automated invoice intake, validation, and approval routing.", "priority": "High", "department": "Finance", "status": "Pending"},
            {"title": "Integrate ERP system connectors", "description": "Connect automation pipeline to ERP system for real-time data sync.", "priority": "Medium", "department": "Engineering", "status": "Pending"},
            {"title": "Configure compliance audit trail", "description": "Ensure all automated financial transactions are logged for audit compliance.", "priority": "High", "department": "Operations", "status": "Pending"},
        ]
        bullets = [
            "• Automate invoice processing and approval workflows to reduce cycle time by 60%",
            "• Implement real-time budget monitoring with automated variance alerts",
            "• Deploy ERP integration for seamless financial data synchronisation",
            "• Establish automated compliance audit trails for regulatory reporting",
            "• Reduce manual data entry errors through intelligent document processing",
        ]
    elif any(k in text for k in ("hr", "onboard", "recruit", "employ", "staff", "people")):
        domain = "HR Process Automation"
        tasks = [
            {"title": "Design employee onboarding workflow", "description": "Create a structured automated onboarding pipeline for new hires.", "priority": "High", "department": "Operations", "status": "Pending"},
            {"title": "Automate document collection", "description": "Implement automated document request and verification for new employees.", "priority": "High", "department": "Operations", "status": "Pending"},
            {"title": "Set up IT provisioning triggers", "description": "Automate IT account creation and access provisioning upon hire confirmation.", "priority": "Medium", "department": "Engineering", "status": "Pending"},
            {"title": "Build onboarding progress dashboard", "description": "Create visibility into onboarding completion rates and bottlenecks.", "priority": "Low", "department": "Management", "status": "Pending"},
        ]
        bullets = [
            "• Automate new employee onboarding to reduce time-to-productivity by 40%",
            "• Implement structured document collection and e-signature workflows",
            "• Trigger IT provisioning automatically upon hire confirmation in HRIS",
            "• Deploy automated welcome communications and schedule coordination",
            "• Build real-time onboarding progress tracking for HR and management visibility",
        ]
    elif any(k in text for k in ("data", "report", "analytics", "dashboard", "insight", "metric")):
        domain = "Data & Analytics Automation"
        tasks = [
            {"title": "Define data pipeline architecture", "description": "Design the end-to-end data ingestion and transformation pipeline.", "priority": "High", "department": "Engineering", "status": "Pending"},
            {"title": "Automate data quality checks", "description": "Implement automated validation rules to detect anomalies and missing data.", "priority": "High", "department": "Engineering", "status": "Pending"},
            {"title": "Build automated reporting schedule", "description": "Configure scheduled report generation and distribution to stakeholders.", "priority": "Medium", "department": "Operations", "status": "Pending"},
            {"title": "Set up stakeholder alert system", "description": "Deploy threshold-based automated alerts for key business metrics.", "priority": "Medium", "department": "Management", "status": "Pending"},
        ]
        bullets = [
            "• Establish automated data ingestion pipeline from all primary business sources",
            "• Implement real-time data quality validation and anomaly detection",
            "• Deploy scheduled reporting with automated stakeholder distribution",
            "• Configure threshold-based alerting for critical business KPIs",
            "• Reduce manual reporting effort by 80% through end-to-end automation",
        ]
    elif any(k in text for k in ("customer", "support", "ticket", "crm", "client", "service")):
        domain = "Customer Operations Automation"
        tasks = [
            {"title": "Automate ticket triage and routing", "description": "Implement AI-powered ticket classification and intelligent routing rules.", "priority": "High", "department": "Operations", "status": "Pending"},
            {"title": "Deploy automated acknowledgement system", "description": "Send immediate automated acknowledgements and SLA timeline updates to customers.", "priority": "High", "department": "Operations", "status": "Pending"},
            {"title": "Build knowledge base integration", "description": "Connect support automation to knowledge base for self-service deflection.", "priority": "Medium", "department": "Engineering", "status": "Pending"},
            {"title": "Configure escalation automation", "description": "Automate escalation triggers based on priority, SLA breach, and sentiment.", "priority": "High", "department": "Management", "status": "Pending"},
        ]
        bullets = [
            "• Implement AI-powered ticket classification to reduce triage time by 70%",
            "• Deploy automated customer acknowledgements and real-time SLA tracking",
            "• Integrate knowledge base for intelligent self-service deflection",
            "• Configure priority-based escalation automation for high-value customers",
            "• Establish CSAT feedback collection automation post-resolution",
        ]
    else:
        domain = "Enterprise Process Automation"
        tasks = [
            {"title": "Map and document current workflows", "description": "Conduct a detailed audit of existing manual processes targeted for automation.", "priority": "High", "department": "Operations", "status": "Pending"},
            {"title": "Define automation requirements", "description": "Gather stakeholder requirements and define measurable automation success criteria.", "priority": "High", "department": "Management", "status": "Pending"},
            {"title": "Design integration architecture", "description": "Architect the integration layer connecting automation with existing enterprise systems.", "priority": "Medium", "department": "Engineering", "status": "Pending"},
            {"title": "Pilot and validate automation", "description": "Run a controlled pilot to validate automation logic before full rollout.", "priority": "Medium", "department": "Operations", "status": "Pending"},
        ]
        bullets = [
            "• Identify and document all manual process steps eligible for automation",
            "• Define measurable KPIs to validate automation ROI and performance",
            "• Design scalable integration architecture aligned with enterprise systems",
            "• Establish change management and stakeholder communication plan",
            "• Plan phased rollout with pilot validation and continuous improvement loop",
        ]

    summary = "\n".join(bullets)

    task_lines = "\n".join(
        f"- {t['title']} ({t['priority']} Priority · {t['department']})"
        for t in tasks
    )

    email_body = f"""Subject: AI Automation Workflow Analysis — {domain}

Dear Team,

I am writing to share the outcomes of the automated workflow analysis processed through the Enterprise AI Automation Assistant pipeline on {now_str}.

Workflow Request:
{user_input[:300]}{"..." if len(user_input) > 300 else ""}

Workflow Analysis Summary:
{summary}

Recommended Action Items:
{task_lines}

Next Steps:
Please review the recommended tasks above and assign ownership to the relevant department leads. All tasks have been logged in the automation dashboard for tracking and accountability.

This communication was automatically generated and processed by the Enterprise AI Automation Assistant. No manual intervention was required in producing this analysis.

Best regards,
Enterprise AI Automation Assistant
AI-Powered Workflow Intelligence Platform"""

    return {
        "summary": summary,
        "tasks": tasks,
        "email": email_body,
        "used_fallback": True,
    }


def parse_ai_response(data: dict, user_input: str) -> tuple[str, list, str]:
    """Parse and validate the Gemini JSON response. Fall back to defaults on bad data."""
    summary = data.get("summary", "")
    tasks = data.get("tasks", [])
    email = data.get("email", "")

    if not isinstance(summary, str) or len(summary.strip()) < 20:
        fallback = build_fallback_response(user_input)
        summary = fallback["summary"]

    if not isinstance(tasks, list) or len(tasks) == 0:
        fallback = build_fallback_response(user_input)
        tasks = fallback["tasks"]

    valid_tasks = []
    for t in tasks:
        if isinstance(t, dict) and "title" in t:
            valid_tasks.append({
                "title": t.get("title", "Review task"),
                "description": t.get("description", "Review and action this task."),
                "priority": t.get("priority", "Medium") if t.get("priority") in ("High", "Medium", "Low") else "Medium",
                "department": t.get("department", "Operations"),
                "status": "Pending",
            })
    if not valid_tasks:
        valid_tasks = build_fallback_response(user_input)["tasks"]

    if not isinstance(email, str) or len(email.strip()) < 50:
        email = build_fallback_response(user_input)["email"]

    return summary, valid_tasks, email


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    workflows = get_all_workflows()
    stats = get_stats()
    return render_template("dashboard.html", workflows=workflows, stats=stats)


@app.route("/process", methods=["POST"])
def process_workflow():
    data = request.get_json(silent=True) or {}
    user_input = data.get("input", "").strip()

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    used_fallback = False

    ai_data = ai_generate_combined(user_input)

    if ai_data is None:
        logger.info("Using intelligent fallback response for input: %.80s...", user_input)
        fb = build_fallback_response(user_input)
        summary = fb["summary"]
        tasks = fb["tasks"]
        email = fb["email"]
        used_fallback = True
    else:
        try:
            summary, tasks, email = parse_ai_response(ai_data, user_input)
        except Exception as exc:
            logger.error("Failed to parse Gemini response: %s — using fallback", exc)
            fb = build_fallback_response(user_input)
            summary, tasks, email = fb["summary"], fb["tasks"], fb["email"]
            used_fallback = True

    try:
        workflow_id = save_workflow(
            user_input=user_input,
            summary=summary,
            tasks=json.dumps(tasks),
            email=email,
        )
    except Exception as exc:
        logger.error("Database save failed: %s", exc)
        workflow_id = None

    response_payload = {
        "success": True,
        "workflow_id": workflow_id,
        "summary": summary,
        "tasks": tasks,
        "email": email,
    }

    if used_fallback:
        response_payload["notice"] = (
            "AI response generated using intelligent fallback mode. "
            "Gemini API is currently unavailable (quota limit or missing API key). "
            "All features remain fully functional."
        )

    return jsonify(response_payload)


@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json(silent=True) or {}
    recipient_email = data.get("recipient_email", "").strip()
    subject = data.get("subject", "").strip()
    email_body = data.get("email_body", "").strip()
    workflow_id = data.get("workflow_id")

    if not recipient_email or not subject or not email_body:
        return jsonify({"error": "Recipient email, subject, and email body are required."}), 400

    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return jsonify({
            "error": (
                "SMTP credentials not configured. "
                "Set SMTP_EMAIL and SMTP_PASSWORD in environment secrets. "
                "Use a Gmail App Password (not your account password)."
            )
        }), 500

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Enterprise AI Automation Assistant <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    msg.attach(MIMEText(email_body, "plain"))

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:24px">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:24px 28px">
          <div style="color:#fff;font-size:18px;font-weight:700">Enterprise AI Automation Assistant</div>
          <div style="color:rgba(255,255,255,0.75);font-size:13px;margin-top:4px">AI-Generated Communication</div>
        </div>
        <div style="padding:28px;color:#1e1e2e;font-size:14px;line-height:1.75;white-space:pre-line">{email_body}</div>
        <div style="background:#f8f8fc;padding:16px 28px;font-size:11px;color:#888;border-top:1px solid #eee">
          This email was generated and sent automatically by the Enterprise AI Automation Assistant · Workflow #{workflow_id or "N/A"}
        </div>
      </div>
    </body></html>
    """
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, recipient_email, msg.as_string())
        logger.info("Email sent to %s (workflow %s)", recipient_email, workflow_id)
    except smtplib.SMTPAuthenticationError:
        return jsonify({
            "error": (
                "Gmail authentication failed. "
                "You must use a Gmail App Password — not your account password. "
                "Generate one at: myaccount.google.com → Security → App Passwords."
            )
        }), 500
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending to %s: %s", recipient_email, exc)
        return jsonify({"error": f"SMTP error: {exc}"}), 500
    except Exception as exc:
        logger.error("Unexpected error sending email: %s", exc)
        return jsonify({"error": f"Failed to send email: {exc}"}), 500

    if N8N_WEBHOOK_URL:
        try:
            http_requests.post(
                N8N_WEBHOOK_URL,
                json={
                    "recipient_email": recipient_email,
                    "subject": subject,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "workflow_id": workflow_id,
                },
                timeout=8,
            )
        except Exception as exc:
            logger.warning("n8n webhook failed (non-blocking): %s", exc)

    if workflow_id:
        try:
            log_activity(
                workflow_id,
                "Email Automation Triggered",
                f"Email sent to {recipient_email} via Gmail SMTP automation pipeline",
            )
        except Exception as exc:
            logger.warning("Failed to log email activity: %s", exc)

    return jsonify({
        "success": True,
        "message": f"Email sent successfully to {recipient_email}!",
    })


@app.route("/data/workflows")
def api_workflows():
    return jsonify(get_all_workflows())


@app.route("/data/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/data/status")
def api_status():
    return jsonify({
        "status": "running",
        "gemini_available": gemini_available,
        "gemini_model": MODEL if gemini_available else None,
        "fallback_mode": not gemini_available,
        "smtp_configured": bool(SMTP_EMAIL and SMTP_PASSWORD),
        "n8n_configured": bool(N8N_WEBHOOK_URL),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Enterprise AI Automation Assistant on port %d", port)
    logger.info("Gemini available: %s | Fallback mode: %s", gemini_available, not gemini_available)
    app.run(host="0.0.0.0", port=port, debug=False)
