# Deploying Snowflake Sharding to the Internet (Free)

This guide gets your app live at a public URL — something like `https://snowflake-sharding.onrender.com` — using **Render.com's free tier**. No credit card required.

---

## Why Render?

Render is the easiest way to host a Python FastAPI app for free. It:
- Auto-detects your Python app
- Gives you a public HTTPS URL
- Redeploys automatically every time you push to GitHub

The one caveat: the free tier **spins down after 15 minutes of inactivity** and takes ~30 seconds to wake up on the next request. For a portfolio demo this is fine — just mention it in your README or add a note on the site.

---

## Step 1 — Push Your Code to GitHub

If you haven't already:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/snowflake-sharding.git
git push -u origin main
```

---

## Step 2 — Create a Render Account

Go to [https://render.com](https://render.com) and sign up with your GitHub account.

---

## Step 3 — New Web Service

1. In the Render dashboard, click **New → Web Service**
2. Connect your GitHub account and select the `snowflake-sharding` repository
3. Render will detect the `render.yaml` file and fill in the settings automatically

If it asks you to set them manually:

| Setting | Value |
|---------|-------|
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free |

4. Click **Create Web Service**

Render will build and deploy. First deploy takes 2–3 minutes.

---

## Step 4 — Your Live URL

Once deployed, Render gives you a URL like:

```
https://snowflake-sharding-xxxx.onrender.com
```

- **Live visualizer**: `https://your-app.onrender.com`
- **API docs**: `https://your-app.onrender.com/docs`

---

## Important: Data Resets on Redeploy

On Render's free tier, the filesystem is **ephemeral** — the `shards/` directory (your SQLite files) is wiped every time the app redeploys or restarts. This means user data resets to zero after each deploy.

**For a portfolio demo this is fine.** Visitors can generate 50–500 fake users and watch the shards fill up in real time. Just add a note:

> *"Data resets on each deploy — click Generate to populate the shards."*

**If you want persistent data**, Render offers a $7/month persistent disk you can mount at the `shards/` path. Or migrate to PostgreSQL (one database per shard → one schema per shard, same routing logic).

---

## Step 5 — Add the Link to Your GitHub Profile

1. Go to your repository on GitHub
2. Click the gear icon next to **About** (top right of the repo page)
3. Paste your Render URL in the **Website** field
4. Add topics: `distributed-systems` `snowflake-id` `sharding` `fastapi` `python` `portfolio`

Now your repo shows a clickable live demo link right at the top. That's the kind of thing that gets noticed.

---

## Alternative: Railway

[Railway.app](https://railway.app) is another option with a slightly more generous free tier.

1. Sign up at railway.app with GitHub
2. New Project → Deploy from GitHub repo
3. Railway auto-detects FastAPI
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Done — you get a `*.railway.app` URL

---

## Local Development (Reminder)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000
```
