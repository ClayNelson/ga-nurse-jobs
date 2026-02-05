# GA Nurse Jobs Scanner

Automated daily scanner for **PRN / Per Diem Infection Control & Infectious Disease** nursing positions in south-central Georgia.

**Live Page:** [claynelson.github.io/ga-nurse-jobs](https://claynelson.github.io/ga-nurse-jobs/)

## How It Works

1. A GitHub Action runs daily at 7:00 AM ET
2. Queries Google Jobs (via SerpAPI) for relevant positions across target cities
3. Filters results by keyword relevance and deduplicates against previously seen postings
4. Publishes a static HTML report to GitHub Pages
5. Sends an email digest with new listings

## Target Areas

- Macon / Warner Robins
- Albany / Americus
- Valdosta / Tifton

## Setup

### 1. SerpAPI Key (Required)

Sign up at [serpapi.com](https://serpapi.com/) — free tier gives 100 searches/month.

Add as repository secret: `SERPAPI_KEY`

### 2. Email Notifications (Optional)

For Gmail, create an [App Password](https://myaccount.google.com/apppasswords) and add these secrets:

| Secret | Value |
|--------|-------|
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | Gmail App Password |
| `EMAIL_TO` | Recipient email(s), comma-separated |

### 3. Enable GitHub Pages

Settings → Pages → Source: Deploy from branch `main`, folder `/docs`

### 4. Manual Run

Actions → Daily Job Scan → Run workflow

## File Structure

```
├── scraper.py              # Main scanner script
├── config.yaml             # Search configuration
├── requirements.txt        # Python dependencies
├── templates/
│   ├── index.html          # GitHub Pages template
│   └── email.html          # Email digest template
├── docs/                   # Generated output
├── data/
│   └── seen_jobs.json      # Deduplication state
└── .github/workflows/
    └── scan.yml            # Daily cron Action
```
