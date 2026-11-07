# 테스트 대상(Mini Cloud Console)을 컨테이너로 실행
FROM python:3.12-slim

WORKDIR /srv
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY app/ app/

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/instances')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
