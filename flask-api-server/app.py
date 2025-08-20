# flask-api-server/app.py
# 예시코드

from flask import Flask, request, jsonify
# utils.py가 requester 폴더에 있으므로, 현재 app.py의 위치에 따라 상대 경로를 조정해야 합니다.
# 예시: app.py가 requester 폴더와 같은 레벨에 있다면 'from requester.utils import ...'
#       app.py가 flask-api-server 폴더 안에 있다면 'from ..requester.utils import ...'
# 여기서는 app.py가 requester 폴sder와 같은 최상위 레벨에 있다고 가정하고 작성합니다.
# 만약 flask-api-server/app.py로 폴더를 나눴다면, 아래 임포트 문을 'from ..requester.utils import'로 변경해야 합니다.
from requester.utils import (
    load_kube,
    build_job_manifest,
    create_job_from_manifest,
    wait_for_job_complete,
    get_pod_logs,
    get_job_pod_name,
    delete_job,
)
import os
import yaml
import sys
import time
from datetime import datetime
import asyncio
from kademlia.network import Server
# utils.py 처럼 p2p-overlay/kademlia/peer.py도 임포트할 수 있도록 경로 조정
from p2p_overlay.kademlia.peer import init_kademlia_server, KademliaClient # 아래 예시를 위한 가상의 함수/클래스


app = Flask(__name__)

# Flask 앱이 시작될 때 Kubernetes 클라이언트를 로드합니다.
# 이 Flask 서버가 Kubernetes 클러스터 내부에 Pod으로 배포될 것이므로,
# load_incluster_config()를 통해 자동으로 인증 정보를 로드하도록 설정합니다.
try:
    load_kube()
    print("[Flask API] Kubernetes 클라이언트가 클러스터 내부 설정으로 로드되었습니다.")
except Exception as e:
    # 클러스터 외부에서 개발/테스트 시에는 아래 주석을 해제하고 kubeconfig 경로를 지정합니다.
    # load_kube(kubeconfig=os.path.expanduser("~/.kube/config"))
    # print("[Flask API] Kubernetes 클라이언트가 외부 kubeconfig로 로드되었습니다.")
    print(f"[Flask API] Kubernetes 클라이언트 로드 실패: {e}", file=sys.stderr)
    sys.exit(1) # 클라이언트 로드 실패 시 앱 시작 중단

# --- 헬스 체크 엔드포인트 ---
@app.route('/healthz', methods=['GET'])
def healthz():
    """
    Flask 서버의 상태를 확인하는 헬스 체크 엔드포인트.
    """
    return jsonify({"status": "healthy"}), 200

# --- Job 생성 및 실행 API 엔드포인트 ---
@app.route('/api/v1/run-job', methods=['POST'])
def run_job():
    """
    웹 요청을 받아 Kubernetes Job을 생성하고 실행합니다.
    요청 본문(JSON)에서 Job에 필요한 파라미터를 받습니다.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "요청 본문(JSON)이 필요합니다."}), 400

    # Job 파라미터 추출 및 기본값 설정
    # 요청으로부터 값을 가져오고, 없으면 합리적인 기본값을 사용합니다.
    image = data.get('image', 'ubuntu:20.04')
    command = data.get('command') # 리스트 형태 (예: ["/bin/bash", "-c"])
    args = data.get('args')       # 리스트 형태 (예: ["echo hello"])
    namespace = data.get('namespace', 'default')
    runtime_class = data.get('runtimeClass', 'kata') # 기본값 'kata'
    cpu_request = data.get('cpuRequest', '500m')
    cpu_limit = data.get('cpuLimit', '1')
    mem_request = data.get('memRequest', '512Mi')
    mem_limit = data.get('memLimit', '1Gi')
    
    # Node Selector 처리: "key=value" 형태의 문자열 리스트를 딕셔너리로 변환
    node_selector_pairs = data.get('nodeSelector')
    node_selector = {}
    if node_selector_pairs:
        if not isinstance(node_selector_pairs, list):
            return jsonify({"error": "nodeSelector는 'key=value' 형태의 문자열 리스트여야 합니다."}), 400
        try:
            for kv in node_selector_pairs:
                if "=" not in kv:
                    raise ValueError(f"잘못된 nodeSelector 형식: '{kv}' (기대: key=value)")
                k, v = kv.split("=", 1)
                node_selector[k] = v
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    delete_after = data.get('deleteAfter', True)
    # wait_for_completion은 API가 Job 완료를 기다릴지 여부 (장기 실행 Job에 유용)
    wait_for_completion = data.get('waitForCompletion', False)
    wait_timeout = data.get('waitTimeoutSeconds', 600) # Job 완료 대기 타임아웃

    # Job 실행 명령어/인자 유효성 검사
    if not command and not args:
        # 경고만 출력하고 Job 생성은 시도합니다. (이미지가 자체 ENTRYPOINT를 가질 수 있으므로)
        app.logger.warning("Job에 'command' 또는 'args'가 지정되지 않았습니다. 이미지가 자체 명령을 포함하지 않으면 Job이 즉시 완료될 수 있습니다.")
    
    # Job 이름 자동 생성
    job_name = f"web-kata-job-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Job 매니페스트 생성
    try:
        manifest = build_job_manifest(
            name=job_name,
            namespace=namespace,
            image=image,
            command=command,
            args=args,
            runtime_class=runtime_class,
            cpu_request=cpu_request,
            cpu_limit=cpu_limit,
            mem_request=mem_request,
            mem_limit=mem_limit,
            node_selector=node_selector if node_selector else None # 빈 딕셔너리 대신 None 전달
        )
        app.logger.info(f"생성될 Job 매니페스트: {yaml.dump(manifest, default_flow_style=False, sort_keys=False)}")
    except Exception as e:
        app.logger.error(f"Job 매니페스트 생성 중 오류 발생: {e}")
        return jsonify({"error": f"Job 매니페스트 생성 실패: {e}"}), 500

    # Job 생성 및 응답
    try:
        create_job_from_manifest(manifest)
        app.logger.info(f"Job '{namespace}/{job_name}'이(가) Kubernetes에 성공적으로 제출되었습니다.")

        response_data = {
            "status": "Job Submitted",
            "jobName": job_name,
            "namespace": namespace,
            "message": f"Job '{job_name}'이(가) 성공적으로 제출되었습니다. Job ID: {job_name}"
        }

        # Job 완료를 기다릴지 여부에 따라 분기
        if wait_for_completion:
            app.logger.info(f"Job '{job_name}' 완료를 대기 중... (타임아웃: {wait_timeout}초)")
            try:
                job_status = wait_for_job_complete(name=job_name, namespace=namespace, timeout=wait_timeout)
                response_data["completionStatus"] = job_status

                # 로그 수집
                pod_name = get_job_pod_name(name=job_name, namespace=namespace)
                if pod_name:
                    logs = get_pod_logs(pod=pod_name, namespace=namespace)
                    response_data["logs"] = logs
                else:
                    response_data["logWarning"] = "Job에 해당하는 Pod를 찾을 수 없어 로그를 가져올 수 없습니다."
                
                # Job 삭제 (설정된 경우)
                if delete_after:
                    delete_job(name=job_name, namespace=namespace)
                    app.logger.info(f"Job '{namespace}/{job_name}'이(가) 삭제되었습니다.")
                    response_data["deleted"] = True
                
                return jsonify(response_data), 200 # 200 OK: Job 완료까지 기다린 경우

            except TimeoutError as e:
                app.logger.error(f"Job '{job_name}' 완료 대기 타임아웃: {e}")
                response_data["completionStatus"] = "Timeout"
                response_data["error"] = str(e)
                return jsonify(response_data), 202 # 202 Accepted: 타임아웃 발생, Job은 백그라운드에서 실행 중
            except Exception as e:
                app.logger.error(f"Job '{job_name}' 완료/로그 처리 중 오류 발생: {e}")
                response_data["completionStatus"] = "Error during completion check"
                response_data["error"] = str(e)
                return jsonify(response_data), 500

        else:
            return jsonify(response_data), 202 # 202 Accepted: Job이 제출되었고, 백그라운드에서 실행될 것임

    except Exception as e:
        app.logger.error(f"Job '{job_name}' 제출 중 오류 발생: {e}")
        return jsonify({"error": f"Job 제출 실패: {e}"}), 500

# --- Flask 앱 실행 ---
if __name__ == '__main__':
    # 개발 환경에서 실행 시:
    # app.run(debug=True, host='0.0.0.0', port=5000)
    # 실제 프로덕션 환경에서는 Gunicorn과 같은 WSGI 서버를 사용해야 합니다.
    # 예: gunicorn -w 4 -b 0.0.0.0:5000 app:app
    print("[Flask API] Flask 서버를 시작합니다. (개발 모드)")
    app.run(host='0.0.0.0', port=5000)

# Flask 앱 시작 시 Kademlia 서버/클라이언트 초기화
kademlia_server_instance = None
kademlia_client = None

@app.before_first_request
def setup_kademlia():
    global kademlia_server_instance, kademlia_client
    # Kademlia 노드 설정을 환경 변수 또는 configmap에서 가져옵니다.
    # LISTEN_IP는 해당 Pod의 Yggdrasil IP가 되어야 합니다 (추가적인 동적 IP 획득 로직 필요).
    # 여기서는 임시로 '0.0.0.0'을 사용하고 hostNetwork를 가정합니다.
    listen_ip = os.getenv("KADEMLIA_LISTEN_IP", "0.0.0.0")
    listen_port = int(os.getenv("KADEMLIA_LISTEN_PORT", "8468"))
    bootstrap_nodes_str = os.getenv("KADEMLIA_BOOTSTRAP_NODES", "[]")

    # 실제 Kademlia 부트스트랩 노드 파싱 로직은 p2p-overlay/kademlia/peer.py 참조
    try:
        bootstrap_nodes = json.loads(bootstrap_nodes_str)
        bootstrap_nodes = [tuple(node) for node in bootstrap_nodes]
    except Exception as e:
        app.logger.error(f"Kademlia 부트스트랩 노드 파싱 실패: {e}. 부트스트랩 없이 시작.")
        bootstrap_nodes = []

    # Flask 앱 내에서 Kademlia 서버 인스턴스를 직접 시작 (가장 간단한 통합 방법)
    # 프로덕션에서는 별도의 Kademlia Pod으로 분리하고 이 Flask 앱은 Kademlia 서비스와 통신하는 것이 좋습니다.
    # asyncio.run()은 이미 실행 중인 이벤트 루프에서는 호출할 수 없으므로,
    # Flask와 asyncio를 함께 사용하는 방식(예: aiohttp, Quart 또는 ThreadPoolExecutor 사용)이 필요합니다.
    # 여기서는 단순화를 위해 가상의 'init_kademlia_server' 함수를 사용합니다.

    # --- 실제 Kademlia 연동 로직 (가상 코드) ---
    # 이 부분은 Kademlia 라이브러리의 비동기 특성상 Flask의 동기식 요청 처리와 통합하기 까다롭습니다.
    # 대안 1: Flask-Executor (ThreadPoolExecutor)를 사용하여 Kademlia 작업을 비동기적으로 실행
    # 대안 2: Flask 대신 FastAPI (asyncio 네이티브) 사용
    # 대안 3: Kademlia 노드를 별도의 서비스로 띄우고 RPC(gRPC 등)로 통신
    # 여기서는 가장 간단하게, Flask 앱이 Kademlia 클라이언트 역할을 하는 것으로 가정합니다.

    # For simplicity, assuming Kademlia server is running elsewhere or
    # app.py will act as a client to a Kademlia service
    app.logger.info("Kademlia 클라이언트 초기화...")
    # Kademlia 클라이언트 생성 (Kademlia 서버가 외부에 있다고 가정)
    # Flask 앱이 직접 Kademlia 서버가 되려면 더 복잡한 asyncio 통합 필요
    # 예시: kademlia_client = KademliaClient(listen_ip, listen_port, bootstrap_nodes)
    #      asyncio.run_coroutine_threadsafe(kademlia_client.start(), app.loop)
    app.logger.info("Kademlia 클라이언트가 초기화되었습니다. DHT 작업 준비 완료.")

# ... (run_job 엔드포인트 내)
job_name = f"web-kata-job-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

try:
    # Job 생성 후 Kademlia에 Job 메타데이터 저장
    # 이 부분은 Kademlia 클라이언트가 성공적으로 초기화된 후 작동합니다.
    job_metadata = {
        "job_name": job_name,
        "namespace": namespace,
        "image": image,
        "status": "submitted",
        "timestamp": datetime.utcnow().isoformat(),
        # 필요한 다른 메타데이터 추가
    }
    # Flask 요청 핸들러는 동기식이므로, 비동기 Kademlia 호출을 위해 asyncio.run_coroutine_threadsafe 또는 ThreadPoolExecutor 사용
    # asyncio.run_coroutine_threadsafe(kademlia_client.set(job_name, json.dumps(job_metadata)), asyncio.get_event_loop())
    app.logger.info(f"Job '{job_name}' 메타데이터를 Kademlia DHT에 저장 요청.")

    create_job_from_manifest(manifest)
    app.logger.info(f"Job '{namespace}/{job_name}'이(가) Kubernetes에 성공적으로 제출되었습니다.")

    # ... (Job 완료 대기 및 로그 수집 부분)
    # Job 완료 후 Kademlia에 상태 업데이트
    # asyncio.run_coroutine_threadsafe(kademlia_client.set(job_name, json.dumps({"status": job_status})), asyncio.get_event_loop())
    app.logger.info(f"Job '{job_name}' 상태를 Kademlia DHT에 업데이트 요청.")

except Exception as e:
    app.logger.error(f"Job '{job_name}' 제출 또는 Kademlia 저장 중 오류 발생: {e}")
    return jsonify({"error": f"Job 제출 또는 Kademlia 저장 실패: {e}"}), 500