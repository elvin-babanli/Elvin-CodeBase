# Admin Dashboard & Analytics Setup

## Overview

The analytics system provides an admin-only dashboard for traffic, visitors, and behavior analysis.

## Setup

### 1. Run migrations

```bash
python manage.py migrate analytics
```

### 2. Create admin account

The dashboard is only visible to `elvinbabanli0@gmail.com`. Create this user:

```bash
python manage.py createsuperuser
```

Use email: `elvinbabanli0@gmail.com` and your chosen password.

### 3. Environment variables

| Key | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | For AI Analysis tab (optional) |
| `ADMIN_DASHBOARD_EMAILS` | Override in settings if needed (default: elvinbabanli0@gmail.com) |

### 4. Daily report (optional)

Run via cron:

```bash
python manage.py send_daily_report
```

Sends summary to `ADMIN_REPORT_EMAIL` (default: elvinbabanli0@gmail.com).

## Access

1. Log in with `elvinbabanli0@gmail.com`
2. Navbar shows "📊 Admin Dashboard"
3. Click to open `/analytics/`
4. Unauthorized users are redirected to home

## Features

- **Overview**: Online visitors, total stats, today's traffic
- **Live**: Real-time online visitors
- **Registered / Guests**: User lists
- **Traffic**: Chart, top pages, top countries
- **Auth events**: Login/register/logout tracked automatically
- **AI Analysis**: OpenAI-based behavior analysis (requires OPENAI_API_KEY)

## Data collected

Only in-app data: page views, sessions, click events, auth events, IP (for geo), user agent. No external profiling.
