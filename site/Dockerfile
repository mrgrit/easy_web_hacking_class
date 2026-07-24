# 빌드 컨텍스트 = 레포 루트 (docker-compose 에서 context: .. 로 지정)
#
# ⚠️ 이 이미지에는 강사용 풀이(solutions/)가 포함됩니다.
#    사이트에서 /solutions 는 **admin 등급 로그인**이 있어야만 열리며(app.py 의
#    @admin_required), 학생 등급에게는 403 입니다. 실습 페이지의 정답·해설도
#    admin 이 아니면 HTML 자체에 렌더링되지 않습니다.
#    그래서 이 이미지는 **강사 서버(hub)** 에만 띄웁니다. 학생 PC 에는 띄우지 마세요.
#    flag 정의 파일(ctf/challenges.yml)은 어떤 경우에도 복사하지 않습니다.
FROM python:3.11-slim
WORKDIR /app
COPY site/requirements.txt ./site/requirements.txt
RUN pip install --no-cache-dir -r site/requirements.txt
COPY site/ ./site/
COPY contents/training ./content/training
COPY downloads ./downloads
COPY solutions ./solutions
ENV PORT=8090
ENV CONTENT_DIR=/app/content/training
ENV DOWNLOADS_DIR=/app/downloads
ENV SOLUTIONS_DIR=/app/solutions
ENV USER_DB=/data/users.db
EXPOSE 8090
CMD ["python", "site/app.py"]
