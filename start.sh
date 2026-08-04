#!/usr/bin/env bash
# Start FastAPI backend in the background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait a few seconds for the backend to boot
sleep 5

# Start Streamlit UI on the port Hugging Face Spaces expects (7860)
export API_BASE_URL="http://localhost:8000"
streamlit run ui/streamlit_app.py --server.port 7860 --server.address 0.0.0.0
