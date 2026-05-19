# Uptime Monitoring Setup

Free external uptime monitoring so you get emailed the moment BookForge goes down.
Takes 5 minutes to set up.

## Option A — UptimeRobot (recommended)

1. Go to **[uptimerobot.com](https://uptimerobot.com)** and create a free account
2. Click **+ Add New Monitor**
3. Fill in:
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `BookForge API`
   - URL: `https://your-app.awsapprunner.com/health`
   - Monitoring Interval: `5 minutes`
4. Under **Alert Contacts**, add your email
5. Click **Create Monitor**

That's it. UptimeRobot pings `/health` every 5 minutes and emails you within
5 minutes of any downtime. Free tier supports up to 50 monitors.

## Option B — BetterStack (nicer UI, also free)

1. Go to **[betterstack.com/uptime](https://betterstack.com/uptime)**
2. Create a free account
3. New monitor → URL: `https://your-app.awsapprunner.com/health`
4. Set check frequency to 3 minutes (free tier minimum)
5. Add your email for alerts

BetterStack also gives you a public status page you can share with users.

## What gets monitored

| Endpoint | What it checks |
|---|---|
| `/health` | API process is running |
| `/ready` | DB + Redis + OpenRouter all reachable |

Point the uptime monitor at `/health` — it never fails due to external
dependencies. Use `/ready` only for internal alerting (App Runner health check).

## Sentry for error tracking

1. Sign up at **[sentry.io](https://sentry.io)** — free tier is 5k errors/month
2. Create a new **Python** project → copy the DSN
3. Add to `backend/.env`: `SENTRY_DSN=https://xxx@sentry.io/yyy`
4. Create a new **Next.js** project → copy the DSN  
5. Add to `frontend/.env.local`: `NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/yyy`

Sentry captures every unhandled exception with full stack trace, request
context, and correlation ID. The free tier is plenty for portfolio scale.

## CloudWatch log retention

Handled by Terraform (`deploy/aws/terraform/modules/cloudwatch/`).
All log groups are set to **7-day retention**.

At 7 days you can debug any incident. At never-expire (AWS default) you pay
forever for logs you'll never read.

**To apply after deploying:**
```bash
make tf-apply
```

## Debugging a user-reported issue

1. Ask the user for the `X-Correlation-ID` from their browser network tab
   (it's on every API response header)
2. Go to AWS CloudWatch → Logs Insights
3. Select all BookForge log groups
4. Run:
   ```
   fields @timestamp, @message
   | filter @message like "THEIR-CORRELATION-ID"
   | sort @timestamp asc
   ```
5. Every log line for their request appears in order

Or search Sentry by the correlation ID if an exception was thrown.
