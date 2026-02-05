#!/usr/bin/env python3
"""
GA Nurse Jobs Scanner
Scrapes job postings for PRN infectious disease / infection control nurse positions
in south-central Georgia. Outputs a static HTML report and optional email digest.
"""

import json
import os
import hashlib
import smtplib
import yaml
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SEEN_FILE = ROOT / "data" / "seen_jobs.json"
OUTPUT_DIR = ROOT / "docs"


def job_id(job: dict) -> str:
    raw = f"{job.get('title','')}-{job.get('company_name','')}-{job.get('location','')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen: dict):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def search_serpapi(query: str, location: str) -> list[dict]:
    if not SERPAPI_KEY:
        print(f"  [WARN] No SERPAPI_KEY set, skipping: {query} in {location}")
        return []
    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "chips": "date_posted:week",
    }
    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("jobs_results", [])
    except Exception as e:
        print(f"  [ERROR] SerpAPI request failed: {e}")
        return []


def normalize_job(raw: dict) -> dict:
    apply_link = ""
    if raw.get("apply_options"):
        apply_link = raw["apply_options"][0].get("link", "")
    elif raw.get("share_link"):
        apply_link = raw["share_link"]

    return {
        "title": raw.get("title", "Unknown"),
        "company_name": raw.get("company_name", "Unknown"),
        "location": raw.get("location", ""),
        "description_snippet": (raw.get("description", ""))[:500],
        "detected_extensions": raw.get("detected_extensions", {}),
        "apply_link": apply_link,
        "via": raw.get("via", ""),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def run_scan() -> tuple[list[dict], list[dict]]:
    seen = load_seen()
    all_jobs = []
    new_jobs = []

    for loc in CONFIG.get("locations", []):
        for q in CONFIG.get("search_queries", []):
            print(f"Searching: '{q}' in '{loc['search_string']}'")
            results = search_serpapi(q, loc["search_string"])
            print(f"  Found {len(results)} results")

            for raw in results:
                job = normalize_job(raw)
                jid = job_id(job)
                job["id"] = jid

                combined = f"{job['title']} {job['description_snippet']}".lower()
                if not any(kw.lower() in combined for kw in CONFIG.get("keywords", [])):
                    continue

                all_jobs.append(job)
                if jid not in seen:
                    seen[jid] = job["scraped_at"]
                    new_jobs.append(job)

    # Deduplicate
    seen_ids = set()
    deduped_all = []
    for j in all_jobs:
        if j["id"] not in seen_ids:
            seen_ids.add(j["id"])
            deduped_all.append(j)
    deduped_new = [j for j in new_jobs if j["id"] in seen_ids]

    save_seen(seen)
    return deduped_all, deduped_new


def render_html(all_jobs, new_jobs):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"))
    tmpl = env.get_template("index.html")
    now = datetime.now(timezone.utc)
    html = tmpl.render(
        all_jobs=all_jobs, new_jobs=new_jobs,
        new_count=len(new_jobs), total_count=len(all_jobs),
        scan_time=now.strftime("%B %d, %Y at %I:%M %p UTC"),
        locations=CONFIG.get("locations", []),
        queries=CONFIG.get("search_queries", []),
    )
    (OUTPUT_DIR / "index.html").write_text(html)
    print(f"Wrote docs/index.html with {len(all_jobs)} jobs ({len(new_jobs)} new)")


def render_email(all_jobs, new_jobs) -> str:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"))
    tmpl = env.get_template("email.html")
    now = datetime.now(timezone.utc)
    return tmpl.render(
        all_jobs=all_jobs, new_jobs=new_jobs,
        new_count=len(new_jobs), total_count=len(all_jobs),
        scan_time=now.strftime("%B %d, %Y at %I:%M %p UTC"),
        page_url=CONFIG.get("page_url", ""),
    )


def send_email(html_body: str, new_count: int):
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    email_to = os.environ.get("EMAIL_TO", "")

    if not all([smtp_user, smtp_pass, email_to]):
        print("[WARN] Email not configured, skipping.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"GA Nurse Jobs: {new_count} new posting{'s' if new_count != 1 else ''}"
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, email_to.split(","), msg.as_string())
        print(f"Email sent to {email_to}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")


def main():
    print("=" * 60)
    print(f"GA Nurse Jobs Scanner - {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    all_jobs, new_jobs = run_scan()
    render_html(all_jobs, new_jobs)

    if CONFIG.get("email_enabled", True):
        html_email = render_email(all_jobs, new_jobs)
        if new_jobs or os.environ.get("FORCE_EMAIL"):
            send_email(html_email, len(new_jobs))
        else:
            print("No new jobs - skipping email.")

    print("Done.")


if __name__ == "__main__":
    main()
