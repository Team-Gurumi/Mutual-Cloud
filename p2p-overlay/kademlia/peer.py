import asyncio
import sys
import logging
import os
import json
import yaml
from typing import Optional, List, Tuple

from kademlia.network import Server
from kademlia.utils import digest
from routing import KademliaRoutingTable # 사용자 정의 라우팅 테이블 클래스 (여기서는 placeholder)
from protocol import KademliaProtocol # 사용자 정의 프로토콜 클래스 (여기서는 placeholder)
from storage import KademliaStorage # 사용자 정의 스토리지 클래스 (여기서는 placeholder)

# 로깅 설정
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log = logging.getLogger('kademlia_node') # 로거 이름 변경
log.addHandler(handler)
log.setLevel(logging.INFO) # DEBUG는 너무 verbose할 수 있으므로 INFO로 시작

# 설정 파일 경로
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')

def load_config(path: str) -> dict:
    """YAML 설정 파일을 로드합니다."""
    if not os.path.exists(path):
        log.warning(f"설정 파일 '{path}'을(를) 찾을 수 없습니다. 기본값을 사용합니다.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

async def run_kademlia_node(
    listen_ip: str, 
    listen_port: int, 
    bootstrap_nodes: Optional[List[Tuple[str, int]]]=None,
    node_id_strategy: str = "random",
    yggdrasil_public_key: Optional[str] = None
):
    """
    Kademlia 노드를 시작하고 P2P 네트워크에 연결합니다.
    """
    node_id = None
    if node_id_strategy == "from_public_key" and yggdrasil_public_key:
        node_id = digest(yggdrasil_public_key.encode('utf-8')) # PublicKey로 ID 생성
        log.info(f"Yggdrasil PublicKey로 Kademlia 노드 ID를 생성했습니다: {node_id.hex()}")
    else:
        log.info("랜덤 Kademlia 노드 ID를 생성합니다.")

    # Kademlia Server 인스턴스 생성
    # 참고: kademlia 라이브러리는 내부적으로 자체 라우팅/프로토콜/스토리지 로직을 가집니다.
    # routing.py, protocol.py, storage.py는 더 깊은 사용자 정의 구현 시 활용될 수 있습니다.
    # 여기서는 라이브러리의 기본 구현을 사용합니다.
    server = Server(node_id=node_id) 
    
    try:
        await server.listen(listen_port, listen_ip)
        log.info(f"Kademlia 노드가 {listen_ip}:{listen_port}에서 리스닝을 시작했습니다.")
    except OSError as e:
        log.error(f"Kademlia 노드 리스닝 실패 (주소 사용 중 또는 권한 문제): {e}")
        sys.exit(1)

    if bootstrap_nodes:
        log.info(f"부트스트랩 노드 {bootstrap_nodes}를 통해 Kademlia 네트워크에 조인 시도 중...")
        try:
            await server.bootstrap(bootstrap_nodes)
            log.info(f"Kademlia 노드가 성공적으로 부트스트랩되었습니다.")
        except Exception as e:
            log.error(f"Kademlia 부트스트랩 실패: {e}. 단독 모드로 계속 실행합니다.")
    else:
        log.info("부트스트랩 노드가 지정되지 않았습니다. 이 노드가 네트워크의 첫 노드가 될 수 있습니다.")

    # 노드가 계속 실행되도록 유지하며, 필요에 따라 DHT 작업 수행
    log.info("Kademlia 노드가 백그라운드에서 실행 중입니다. 데이터 저장/조회 준비 완료.")
    
    # --- 테스트 데이터 저장 및 조회 예시 (옵션) ---
    # 실제 사용 시에는 이 부분을 외부 API 호출 등으로 대체합니다.
    # 예: "job_id": "job_status"
    test_key = "mutual-cloud-job-example-1"
    test_value = json.dumps({
        "status": "pending", 
        "requester_id": "client-abc",
        "timestamp": datetime.now().isoformat()
    })
    await server.set(test_key, test_value)
    log.info(f"테스트 데이터 '{test_key}' = '{test_value}'를 DHT에 저장했습니다.")

    await asyncio.sleep(5) # 데이터 전파를 위해 잠시 대기

    retrieved_value = await server.get(test_key)
    if retrieved_value:
        log.info(f"테스트 데이터 '{test_key}' 조회 결과: '{retrieved_value}'")
    else:
        log.warning(f"테스트 데이터 '{test_key}'를 DHT에서 찾을 수 없습니다.")

    # 노드가 종료되지 않고 계속 P2P 네트워크에서 활동하도록 유지
    try:
        while True:
            await asyncio.sleep(3600) # 1시간마다 유지 (네트워크 유지 활동은 라이브러리가 알아서 함)
    except asyncio.CancelledError:
        log.info("Kademlia 노드 실행이 취소되었습니다.")
    finally:
        server.stop()
        log.info("Kademlia 노드가 종료되었습니다.")

if __name__ == '__main__':
    # 설정 파일 로드 (환경 변수가 우선)
    config_data = load_config(DEFAULT_CONFIG_PATH)

    LISTEN_IP = os.getenv("KADEMLIA_LISTEN_IP", "0.0.0.0") 
    LISTEN_PORT = int(os.getenv("KADEMLIA_LISTEN_PORT", config_data.get("listen_port", 8468)))
    NODE_ID_STRATEGY = os.getenv("KADEMLIA_NODE_ID_STRATEGY", config_data.get("node_id_strategy", "random"))
    YGGDRASIL_PUBLIC_KEY = os.getenv("YGGDRASIL_PUBLIC_KEY") # Yggdrasil 설치 후 얻은 공개키

    # 부트스트랩 노드 목록 (환경 변수가 우선, JSON 형식 문자열)
    bootstrap_nodes_str = os.getenv("KADEMLIA_BOOTSTRAP_NODES", json.dumps(config_data.get("bootstrap_nodes", [])))
    BOOTSTRAP_NODES = None
    if bootstrap_nodes_str:
        try:
            parsed_nodes = json.loads(bootstrap_nodes_str)
            if not isinstance(parsed_nodes, list):
                raise ValueError("부트스트랩 노드는 리스트여야 합니다.")
            BOOTSTRAP_NODES = []
            for node in parsed_nodes:
                if isinstance(node, list) and len(node) == 2 and isinstance(node[0], str) and isinstance(node[1], int):
                    BOOTSTRAP_NODES.append(tuple(node)) 
                else:
                    raise ValueError(f"각 부트스트랩 노드는 [IP_STRING, PORT_INT] 형식이어야 합니다: {node}")
        except Exception as e:
            log.error(f"KADEMLIA_BOOTSTRAP_NODES 환경 변수 파싱 오류: {e}. 부트스트랩 없이 시작합니다.")
            BOOTSTRAP_NODES = None
    
    log.info(f"Kademlia 노드 설정: IP={LISTEN_IP}, Port={LISTEN_PORT}, 부트스트랩={BOOTSTRAP_NODES}")
    log.info(f"노드 ID 전략: {NODE_ID_STRATEGY}")

    try:
        asyncio.run(run_kademlia_node(
            LISTEN_IP, 
            LISTEN_PORT, 
            BOOTSTRAP_NODES, 
            NODE_ID_STRATEGY, 
            YGGDRASIL_PUBLIC_KEY
        ))
    except KeyboardInterrupt:
        log.info("사용자 요청으로 Kademlia 노드를 종료합니다.")