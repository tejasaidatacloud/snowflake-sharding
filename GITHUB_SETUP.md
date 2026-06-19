# GitHub Setup Guide

Run these commands in your terminal from inside the `snowflake-sharding` folder:

## 1. Initialize git (if not already done)
```bash
cd ~/Downloads/snowflake-sharding
git init
git add .
git commit -m "Initial commit: Snowflake Sharding Live Visualizer"
```

## 2. Create a GitHub repo
Go to https://github.com/new and create a repo named `snowflake-sharding` (public, no README).

## 3. Push
```bash
git remote add origin https://github.com/YOUR_USERNAME/snowflake-sharding.git
git branch -M main
git push -u origin main
```

## 4. Deploy to Render (free public URL)
1. Go to https://render.com → sign up with GitHub
2. Click **New → Web Service**
3. Select your `snowflake-sharding` repo
4. Render reads `render.yaml` automatically
5. Click **Create Web Service**
6. Wait ~2 min → your URL appears at the top (e.g. `https://snowflake-sharding.onrender.com`)

## 5. Update your LinkedIn post
Replace `[YOUR_RENDER_URL]` and `[YOUR_USERNAME]` in `linkedin_post.md` with your real URLs.
