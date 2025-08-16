import os
import time
from typing import Optional, Dict, List

from kubernetes import client, config, utils
from kubernetes.client import ApiException
from kubernetes.stream import stream # 현재 사용되지 않으나, 향후 exec 등 필요시 유용
import yaml


def load_kube(kubeconfig: Optional[str] = None) -> None:
    """
    kubeconfig 경로로 클라이언트 로드. None이면 환경에서 자동 탐색.
    """
    if kubeconfig:
        kubeconfig = os.path.expanduser(kubeconfig)
        # config_file=kubeconfig 대신 path=[kubeconfig] 사용 시 여러 경로 탐색 가능
        config.load_kube_config(config_file=kubeconfig)
    else:
        try:
            # 클러스터 내부 실행 시
            config.load_incluster_config()
        except config.ConfigException:
            # 로컬 환경 기본 경로 시도 (예: ~/.kube/config)
            config.load_kube_config()


def build_job_manifest(
    name: str,
    namespace: str,
    image: str,
    command: Optional[List[str]],
    args: Optional[List[str]],
    runtime_class: Optional[str],
    cpu_request: str,
    cpu_limit: str,
    mem_request: str,
    mem_limit: str,
    node_selector: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    간단한 batch/v1 Job 매니페스트 생성.
    runtimeClassName을 지정하여 Kata VM 격리 실행.
    """
    container = {
        "name": "runner",
        "image": image,
        "resources": {
            "requests": {"cpu": cpu_request, "memory": mem_request},
            "limits": {"cpu": cpu_limit, "memory": mem_limit}, # <-- 여기 오타 수정
        },
    }
    if command:
        container["command"] = command
    if args:
        container["args"] = args

    pod_spec = {
        "restartPolicy": "Never", # Job의 Pod는 완료되면 재시작하지 않아야 함
        "containers": [container],
    }
    if runtime_class:
        pod_spec["runtimeClassName"] = runtime_class
    if node_selector:
        pod_spec["nodeSelector"] = node_selector

    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "backoffLimit": 0, # 실패 시 재시도 횟수 (0으로 설정하여 실패 즉시 종료)
            "template": {"spec": pod_spec},
        },
    }
    return manifest


def apply_yaml(path: str, namespace: str) -> List[Dict]:
    """
    주어진 YAML(하나 혹은 다중 문서)을 클러스터에 적용.
    """
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    k8s_client = client.ApiClient()
    created = []
    for doc in docs:
        if not doc: # 빈 문서 스킵
            continue
        # kind가 Job인 경우에만 생성된 Job 객체를 반환하도록 추가 로직 고려 가능 (현재는 모든 생성된 문서 반환)
        utils.create_from_dict(k8s_client, data=doc, namespace=namespace)
        created.append(doc)
    return created


def create_job_from_manifest(manifest: Dict) -> Dict:
    """
    Job 리소스 생성.
    """
    batch = client.BatchV1Api()
    ns = manifest["metadata"]["namespace"]
    # Job 생성 시 반환되는 응답 객체를 Dict로 변환하여 반환 (유용할 수 있음)
    return batch.create_namespaced_job(namespace=ns, body=manifest).to_dict()


def wait_for_job_complete(name: str, namespace: str, timeout: int = 600) -> str:
    """
    Job 완료(Complete/Failed)까지 대기. 상태 문자열 반환.
    """
    batch = client.BatchV1Api()
    started = time.time()
    while True:
        try:
            job = batch.read_namespaced_job(name=name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                raise RuntimeError(f"Job {namespace}/{name}을(를) 찾을 수 없습니다. (오류 코드: 404)")
            raise # 다른 ApiException은 다시 발생시킴

        # Job의 status.conditions에서 Complete 또는 Failed 상태 확인
        c = job.status.conditions or []
        for cond in c:
            if cond.type == "Complete" and cond.status == "True":
                return "Complete"
            if cond.type == "Failed" and cond.status == "True":
                # Job이 실패한 경우, Failure 메시지를 포함하여 반환할 수도 있음 (선택 사항)
                return f"Failed: {cond.message if cond.message else 'Unknown reason'}"

        if time.time() - started > timeout:
            raise TimeoutError(f"Job {namespace}/{name} 완료 대기 타임아웃 발생 ({timeout}초)")

        time.sleep(2) # 2초 간격으로 폴링


def get_job_pod_name(name: str, namespace: str) -> Optional[str]:
    """
    Job이 생성한 Pod 이름을 하나 반환.
    Job의 `.spec.selector`를 사용하여 정확한 Pod를 찾음.
    """
    batch = client.BatchV1Api()
    core = client.CoreV1Api()
    
    try:
        job = batch.read_namespaced_job(name=name, namespace=namespace)
        # Job의 selector를 사용하여 Pod를 필터링
        # Job Selector는 일반적으로 "controller-uid=<job-uid>" 형태
        if job.spec.selector and job.spec.selector.match_labels:
            label_selector = ",".join([f"{k}={v}" for k, v in job.spec.selector.match_labels.items()])
            pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
            if pods.items:
                # Job은 여러 개의 Pod를 가질 수 있지만, 일반적으로 하나만 성공하면 됨.
                # 로그를 위해 첫 번째 Pod의 이름을 반환.
                return pods.items[0].metadata.name
    except ApiException as e:
        if e.status != 404: # Job이 없으면 무시하고 None 반환
            print(f"Error fetching job for pod name: {e}", file=sys.stderr)
    return None


def get_pod_logs(pod: str, namespace: str, container: Optional[str] = None) -> str:
    """
    Pod 로그를 문자열로 반환.
    """
    core = client.CoreV1Api()
    try:
        return core.read_namespaced_pod_log(
            name=pod,
            namespace=namespace,
            container=container, # 컨테이너 이름을 지정하지 않으면 기본 컨테이너의 로그를 가져옴
            follow=False, # 실시간 스트리밍 대신 현재까지의 로그를 가져옴
            tail_lines=1000, # 마지막 1000줄만 가져옴
        )
    except ApiException as e:
        # 로그를 가져오는 데 실패했을 때 빈 문자열을 반환하여 호출하는 쪽에서 처리하기 용이하게 함.
        print(f"Pod '{pod}'의 로그를 가져오는 데 실패했습니다: {e}", file=sys.stderr)
        return "" # 오류 메시지 대신 빈 문자열 반환


def delete_job(name: str, namespace: str) -> None:
    """
    Job 및 하위 Pod 삭제.
    """
    batch = client.BatchV1Api()
    # Foreground Propagation Policy는 Job 삭제 시 Pod도 함께 삭제되도록 보장합니다.
    propagation = client.V1DeleteOptions(propagation_policy="Foreground")
    try:
        batch.delete_namespaced_job(name=name, namespace=namespace, body=propagation)
    except ApiException as e:
        if e.status != 404: # Job이 이미 없으면(404) 오류로 처리하지 않음
            raise # 다른 종류의 API 오류는 다시 발생시킴