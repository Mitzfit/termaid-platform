# Backend image. Build the frontend separately (npm run build) and mount/copy
# frontend/dist, or extend this with a multi-stage Node build.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY frontend/dist/ frontend/dist/
EXPOSE 8000
# run migrations then serve
CMD sh -c "cd backend && alembic upgrade head && cd .. && uvicorn backend.main:app --host 0.0.0.0 --port 8000"
