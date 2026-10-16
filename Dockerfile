FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data
COPY app.py agent.py store.py sample_data.py ./
COPY .streamlit/config.toml .streamlit/config.toml
USER appuser
ENV PYTHONUNBUFFERED=1
ENV CRM_DB_PATH=/app/data/crm.db
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8501') + '/_stcore/health', timeout=3)"
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --browser.gatherUsageStats=false"]
