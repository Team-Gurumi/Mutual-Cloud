# Python 공식 이미지 사용
FROM python:3.9-slim-buster

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 의존성 설치
COPY flask-api-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사 (requester 폴더까지 포함하여 복사)
# 이렇게 하면 app.py에서 requester/utils.py를 쉽게 임포트할 수 있습니다.
COPY requester /app/requester
COPY flask-api-server/app.py /app/app.py

# 포트 노출 (Flask 기본 포트 5000)
EXPOSE 5000

# Gunicorn을 사용하여 Flask 앱 실행 (프로덕션 권장)
# app:app은 app.py 파일 내의 Flask 인스턴스 이름이 'app'임을 의미합니다.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]