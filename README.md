# Enterprise AI Automation Assistant

AI-powered workflow planning, task generation & communication automation — built with Flask + Google Gemini.

## Quick Start (Local)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up your environment
```bash
cp .env.example .env
```
Open `.env` and fill in your values:
- **GEMINI_API_KEY** — get free at https://aistudio.google.com/apikey
- **SMTP_EMAIL** — your Gmail address
- **SMTP_PASSWORD** — Gmail App Password (see below)

### 3. Run the app
```bash
python app.py
```
Open http://localhost:5000 in your browser.

---

## Gmail App Password Setup

You MUST use an App Password, not your regular Gmail password.

1. Go to https://myaccount.google.com
2. Security → 2-Step Verification → turn ON
3. Security → App Passwords
4. App: **Mail** | Device: **Other** → type `Flask App` → **Generate**
5. Copy the 16-character password into `SMTP_PASSWORD` in your `.env` file

---

## Features

- **AI Workflow Summary** — Gemini analyses your request and generates a professional summary
- **Task Generation** — Extracts 4 recommended tasks with priorities and department assignments
- **Communication Draft** — Generates a professional email draft
- **Email Sending** — Sends the draft via Gmail SMTP
- **Dashboard** — Analytics view of all past workflows and activity logs
- **n8n Integration** — Optional webhook trigger for automation pipelines
- **Fallback Mode** — App works even when Gemini quota is exceeded

---

## Project Structure

```
flask-app/
├── app.py              # Main Flask application + Gemini integration
├── database.py         # SQLite operations
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template (copy to .env)
├── templates/
│   ├── index.html      # Main AI assistant page
│   └── dashboard.html  # Analytics dashboard
└── static/
    ├── style.css       # Custom dark UI styles
    └── script.js       # Frontend logic
```

---

## Tech Stack

- **Flask 3.0** — Python web framework
- **Google Gemini** (`gemini-1.5-flash`) — AI model
- **SQLite** — Local database for workflow history
- **Bootstrap 5** — UI framework
- **Gmail SMTP** — Email delivery
