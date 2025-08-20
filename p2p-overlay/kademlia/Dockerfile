# Python 공식 이미지 사용
FROM python:3.9-slim-buster

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 의존성 설치
COPY p2p-overlay/kademlia/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kademlia 노드 스크립트 복사
# peer.py와 함께 config.yaml도 복사 (필요한 경우)
COPY p2p-overlay/kademlia/peer.py .
COPY p2p-overlay/kademlia/config.yaml . # config.yaml도 이미지에 포함

# Kademlia는 UDP 8468 포트를 사용 (설정 가능)
EXPOSE 8468/udp

# Kademlia 노드 실행
# CMD에서 환경변수를 사용하여 LISTEN_IP, LISTEN_PORT, BOOTSTRAP_NODES 설정
CMD ["python3", "peer.py"]