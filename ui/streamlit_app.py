"""
ui/streamlit_app.py — YouTube Automation Dashboard

5 tabs:
  💡 Idea Explorer  — ranked trending ideas, pick & trigger pipeline
  🎬 Video Queue    — job list with stage progress
  📝 Review         — video preview + approve/reject for flagged videos
  📊 Analytics      — upload history + YouTube stats
  ⚙️ Settings       — API key config, scheduling info
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import streamlit as st
from streamlit.components.v1 import html as st_html
import subprocess
import socket
import sys

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

if not is_port_in_use(8000):
    print("Booting up FastAPI Backend...")
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
    time.sleep(3)

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
st.set_page_config(
    page_title="YT Automation Dashboard",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)
import streamlit_authenticator as stauth

# Fetch credentials from backend
try:
    r = httpx.get(f"{API_BASE}/api/auth/users", timeout=5)
    credentials = r.json()
except Exception as e:
    st.error(f"Failed to fetch users: {e}")
    st.stop()

authenticator = stauth.Authenticate(
    credentials,
    "yt_automation_dashboard",
    "stauth_cookie",
    cookie_expiry_days=30,
)

# Render login widget
authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")
    st.stop()

# If authenticated, store username for API calls
USERNAME = st.session_state["username"]
st.sidebar.write(f"Logged in as: **{USERNAME}**")
authenticator.logout("Logout", "sidebar")
# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: #0e1117; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        background: #1c1f2e; border-radius: 10px; padding: 8px 20px;
        color: #8b93a7; font-weight: 500; border: 1px solid #2d3147;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #ff5722, #ff9800);
        color: white !important; border: none;
    }
    .idea-card {
        background: #1a1d2e; border: 1px solid #2d3147; border-radius: 14px;
        padding: 1.2rem 1.4rem; margin-bottom: 0.8rem;
        transition: border-color 0.2s;
    }
    .idea-card:hover { border-color: #ff5722; }
    .score-bar-container { background: #2d3147; border-radius: 6px; height: 8px; overflow: hidden; }
    .score-bar { background: linear-gradient(90deg, #ff5722, #ff9800); height: 8px; border-radius: 6px; }
    .status-badge {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 12px; font-weight: 600;
    }
    .status-queued    { background: #1e3a5f; color: #64b5f6; }
    .status-generating{ background: #1a3040; color: #4fc3f7; }
    .status-review    { background: #3d2b00; color: #ffb300; }
    .status-approved  { background: #1a3a1a; color: #66bb6a; }
    .status-uploading { background: #2d1b4e; color: #ce93d8; }
    .status-done      { background: #143314; color: #a5d6a7; }
    .status-failed    { background: #3a1a1a; color: #ef9a9a; }
    div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(endpoint: str) -> dict | None:
    try:
        r = httpx.get(f"{API_BASE}{endpoint}", headers={"X-User-ID": USERNAME}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(endpoint: str, data: dict | None = None) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}{endpoint}", json=data or {}, headers={"X-User-ID": USERNAME}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def status_badge(status: str) -> str:
    return f'<span class="status-badge status-{status}">{status.upper()}</span>'


def score_bar(score: float) -> str:
    pct = int(score * 100)
    color = "#66bb6a" if score >= 0.80 else "#ffb300" if score >= 0.60 else "#ef5350"
    return f"""
    <div class="score-bar-container">
        <div style="background:{color};height:8px;border-radius:6px;width:{pct}%"></div>
    </div>
    <span style="font-size:12px;color:#8b93a7">{pct}% confidence</span>
    """


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;padding:1rem 0 0.5rem">
  <span style="font-size:2.2rem">🎬</span>
  <div>
    <h1 style="margin:0;font-size:1.8rem;font-weight:700;color:#fff">YouTube Automation</h1>
    <p style="margin:0;font-size:13px;color:#8b93a7">Idea → Script → Voice → Video → Upload</p>
  </div>
</div>
""", unsafe_allow_html=True)

tab_ideas, tab_queue, tab_review, tab_analytics, tab_settings = st.tabs(
    ["💡 Idea Explorer", "🎬 Video Queue", "📝 Review", "📊 Analytics", "⚙️ Settings"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: IDEA EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ideas:
    st.markdown("### ✍️ Custom Video")
    custom_topic = st.text_input("Enter a custom video topic (leave blank for default):", placeholder="e.g. 5 Secret Python Features You Must Know in 2026")
    if st.button("🚀 Create Custom Short", type="primary", use_container_width=False):
        final_topic = custom_topic.strip() if custom_topic.strip() else "5 Secret Python Features You Must Know in 2026"
        result = api_post("/api/pipeline/run", {
            "topic": final_topic,
            "angle": "Educational Tech Tips",
        })
        if result:
            st.success(f"Custom Pipeline started for '{final_topic}'! Job ID: `{result['job_id']}`")
            
    st.markdown("---")

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown("### 💡 Trending Ideas")
        st.caption("Multi-source aggregation: Google Trends · YouTube · Reddit · HackerNews — scored by Gemini Flash")
    with col_h2:
        if st.button("🔄 Refresh Ideas", use_container_width=True):
            api_post("/api/ideas/refresh")
            st.success("Refresh triggered! Check back in ~30 seconds.")

    ideas_data = api_get("/api/ideas")
    ideas = ideas_data.get("ideas", []) if ideas_data else []

    if not ideas:
        st.info("No ideas available yet. Click **Refresh Ideas** to fetch trending topics.")
    else:
        for i, idea in enumerate(ideas):
            combined = idea.get("combined_score", 0)
            virality = idea.get("virality_score", 0)
            niche_rel = idea.get("niche_relevance", 0)

            with st.container():
                st.markdown(f"""
                <div class="idea-card">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div style="flex:1">
                      <div style="font-size:15px;font-weight:600;color:#e8eaf6;margin-bottom:4px">
                        #{i+1} &nbsp; {idea.get("title","—")}
                      </div>
                      <div style="font-size:12px;color:#8b93a7;margin-bottom:8px">
                        💡 {idea.get("suggested_angle","No angle suggested")}
                      </div>
                      <div style="display:flex;gap:16px;font-size:12px;color:#8b93a7">
                        <span>🎯 Niche: <b style="color:#90caf9">{niche_rel:.0%}</b></span>
                        <span>🔥 Virality: <b style="color:#ff9800">{virality:.0%}</b></span>
                        <span>⭐ Combined: <b style="color:#66bb6a">{combined:.0%}</b></span>
                      </div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                with col_btn1:
                    if st.button(f"🚀 Create Short", key=f"run_{i}"):
                        result = api_post("/api/pipeline/run", {
                            "topic": idea["title"],
                            "angle": idea.get("suggested_angle", ""),
                        })
                        if result:
                            st.success(f"Pipeline started! Job ID: `{result['job_id']}`")
                with col_btn2:
                    if st.button(f"⏭️ Skip", key=f"skip_{i}"):
                        st.info("Skipped.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: VIDEO QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_queue:
    st.markdown("### 🎬 Video Production Queue")
    st.caption("Real-time status of all pipeline jobs")

    col_r1, col_r2 = st.columns([5, 1])
    with col_r2:
        auto_refresh = st.toggle("Auto-refresh", value=False)

    videos_data = api_get("/api/videos")
    videos = videos_data.get("videos", []) if videos_data else []

    if not videos:
        st.info("No jobs yet. Go to **Idea Explorer** to start a pipeline.")
    else:
        # Summary metrics
        status_counts = {}
        for v in videos:
            s = v.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        mcols = st.columns(5)
        for idx, (s, label) in enumerate([("done","✅ Done"), ("review","⚠️ Review"), ("generating","⚡ Active"), ("failed","❌ Failed"), ("uploading","📤 Uploading")]):
            mcols[idx].metric(label, status_counts.get(s, 0))

        st.divider()

        for v in videos:
            status = v.get("status", "unknown")
            confidence = v.get("confidence_score", 0)
            yt_id = v.get("youtube_video_id", "")

            col_t, col_s, col_c, col_act = st.columns([4, 1.5, 1.5, 1.5])
            with col_t:
                st.markdown(f"**{v.get('topic','—')[:70]}**")
                st.caption(f"Job: `{v['id'][:8]}...`")
            with col_s:
                st.markdown(status_badge(status), unsafe_allow_html=True)
            with col_c:
                if confidence > 0:
                    st.markdown(score_bar(confidence), unsafe_allow_html=True)
            with col_act:
                if yt_id:
                    st.markdown(f"[▶ Watch](https://youtu.be/{yt_id})")
                elif status == "review":
                    st.markdown("👉 Check **Review** tab")
            st.divider()

    if auto_refresh:
        time.sleep(5)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: REVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_review:
    st.markdown("### 📝 Human Review Queue")
    st.caption("Videos that scored below auto-approve threshold — review before publishing")

    videos_data = api_get("/api/videos")
    all_videos = videos_data.get("videos", []) if videos_data else []
    review_videos = [v for v in all_videos if v.get("status") == "review"]

    if not review_videos:
        st.success("✅ Nothing to review — all videos were auto-approved or are still processing.")
    else:
        for v in review_videos:
            job_id = v["id"]
            st.markdown(f"#### 📹 {v.get('topic','—')[:80]}")
            st.markdown(score_bar(v.get("confidence_score", 0)), unsafe_allow_html=True)

            # Pipeline status detail
            detail = api_get(f"/api/pipeline/status/{job_id}")

            col_vid, col_actions = st.columns([3, 1])

            with col_vid:
                # Show video if file exists
                video_path = detail.get("video_path", "") if detail else ""
                thumb_path = detail.get("thumbnail_path", "") if detail else ""
                if video_path and Path(video_path).exists():
                    st.markdown("**🎬 Video Preview (9:16 Shorts)**")
                    st.video(video_path)
                else:
                    st.info("Video file preview not available on server.")

                if thumb_path and Path(thumb_path).exists():
                    st.markdown("**🖼️ Generated Thumbnail (1280x720 HD)**")
                    st.image(thumb_path, use_container_width=True)

            with col_actions:
                st.markdown("**Actions**")

                # SEO metadata editing
                seo_raw = detail.get("seo_json", "{}") if detail else "{}"
                try:
                    seo = json.loads(seo_raw) if isinstance(seo_raw, str) else seo_raw
                except Exception:
                    seo = {}

                new_title = st.text_input("Title", value=seo.get("title", ""), key=f"title_{job_id}")
                new_desc = st.text_area("Description", value=seo.get("description", ""), key=f"desc_{job_id}", height=100)

                col_approve, col_reject = st.columns(2)
                with col_approve:
                    if st.button("✅ Approve & Upload", key=f"approve_{job_id}", use_container_width=True):
                        result = api_post(f"/api/video/{job_id}/approve")
                        if result:
                            st.success("Uploading to YouTube...")
                with col_reject:
                    if st.button("❌ Reject", key=f"reject_{job_id}", use_container_width=True):
                        result = api_post(f"/api/video/{job_id}/reject")
                        if result:
                            st.error("Job rejected.")
            st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    st.markdown("### 📊 Published Videos")
    videos_data = api_get("/api/videos")
    all_videos = videos_data.get("videos", []) if videos_data else []
    done_videos = [v for v in all_videos if v.get("status") == "done" and v.get("youtube_video_id")]

    if not done_videos:
        st.info("No published videos yet.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Published", len(done_videos))
        auto_count = sum(1 for v in done_videos if v.get("auto_approved"))
        col2.metric("Auto-Approved", auto_count)
        col3.metric("Manual Review", len(done_videos) - auto_count)

        st.divider()
        for v in done_videos:
            yt_id = v["youtube_video_id"]
            col_t, col_id, col_link = st.columns([4, 2, 1])
            col_t.markdown(f"**{v.get('topic','—')[:60]}**")
            col_id.code(yt_id)
            col_link.markdown(f"[▶ Watch](https://youtu.be/{yt_id})")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("### ⚙️ Configuration")
    st.caption("Set your API keys and preferences in the `.env` file on the server. Restart the API after changes.")

    st.markdown("#### 🔐 My Credentials")
    uploaded_file = st.file_uploader("Upload your personal client_secrets.json (Google OAuth)", type="json")
    if uploaded_file is not None:
        file_contents = uploaded_file.getvalue().decode("utf-8")
        try:
            json.loads(file_contents) # Validate JSON
            if st.button("Save Secrets to Database"):
                r = api_post("/api/auth/users/secrets", data={"username": USERNAME, "client_secrets_json": file_contents})
                if r and r.get("status") == "success":
                    st.success("Successfully saved to database!")
        except Exception:
            st.error("Invalid JSON file.")

    with st.expander("📋 Required API Keys", expanded=True):
        st.markdown("""
| Key | Where to Get | Cost |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Free |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) | Free |
| `PIXABAY_API_KEY` | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | Free |
| `REDDIT_CLIENT_ID` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps/) | Free |
| YouTube OAuth | Google Cloud Console | Free |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io) | Optional paid |
        """)

    with st.expander("⏰ Scheduling"):
        st.markdown("""
- **Idea Explorer** runs every **6 hours** automatically (APScheduler cron).
- Use the **🔄 Refresh Ideas** button in the Idea Explorer tab to run manually.
- Videos that score ≥ **80% confidence** are auto-approved and uploaded.
- Videos below 80% appear in the **Review** tab.
        """)

    with st.expander("📁 File Locations (Server)"):
        st.code("""
output/     ← Rendered videos + audio + thumbnails  
cache/      ← Cached stock footage clips  
music/      ← Royalty-free background music (add .mp3/.wav here)  
data/       ← SQLite database (db.sqlite3)  
prompts/    ← Jinja2 niche script templates  
        """, language="text")

    with st.expander("🔗 API Reference"):
        st.markdown(f"""
FastAPI docs: [{API_BASE}/docs]({API_BASE}/docs)

Key endpoints:
- `POST /api/pipeline/run` — Start a new video job
- `GET /api/ideas` — Get trending ideas
- `GET /api/videos` — List all jobs
- `POST /api/video/{{id}}/approve` — Approve & upload
        """)
