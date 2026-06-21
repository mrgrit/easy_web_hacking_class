# 빌드 컨텍스트 = 레포 루트 (docker-compose 에서 context: .. 로 지정)
# 학생에게 보여도 되는 것만 이미지에 복사한다 — solutions/ 와 flag 정의는 복사하지 않는다.
FROM python:3.11-slim
WORKDIR /app
COPY site/requirements.txt ./site/requirements.txt
RUN pip install --no-cache-dir -r site/requirements.txt
COPY site/ ./site/
COPY contents/training ./content/training
COPY downloads ./downloads
ENV PORT=8090
ENV CONTENT_DIR=/app/content/training
ENV DOWNLOADS_DIR=/app/downloads
EXPOSE 8090
CMD ["python", "site/app.py"]
