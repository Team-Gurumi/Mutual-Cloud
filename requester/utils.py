import os
import time
from typing import Optional, Dict, List

from kubernetes import client, config, utils
from kubernetes.client import ApiException
from kubernetes.stream import stream
import yaml


def load_kube(kubeconfig: Optional[str] = None) -> None:
    """
    kubeconfig 경로로 클라이언트 로드. None이면 환경에서 자동 탐색.
    """
    if kubeconfig:
        kubeconfig = os.path.expanduser(kubeconfig)
        config.load_kube_config(config_file=kubeconfig)
    else:
        # 클러스터 내부 실행 시
        try:
            config.load_incluster_config()
        except config.ConfigException:
            # 로컬 환경 기본 경로 시도
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
            "limits": {"cpu": cpu_limit, "memory": mem_limit},
        },
    }
    if command:
        container["command"] = command
    if args:
        container["args"] = args

    pod_spec = {
        "restartPolicy": "Never",
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
            "backoffLimit": 0,
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
        if not doc:
            continue
        utils.create_from_dict(k8s_client, data=doc, namespace=namespace)
        created.append(doc)
    return created


def create_job_from_manifest(manifest: Dict) -> Dict:
    """
    Job 리소스 생성.
    """
    batch = client.BatchV1Api()
    ns = manifest["metadata"]["namespace"]
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
                raise RuntimeError(f"Job {namespace}/{name} not found")
            raise

        c = job.status.conditions or []
        for cond in c:
            if cond.type == "Complete" and cond.status == "True":
                return "Complete"
            if cond.type == "Failed" and cond.status == "True":
                return "Failed"

        if time.time() - started > timeout:
            raise TimeoutError(f"Job {namespace}/{name} wait timeout ({timeout}s)")

        time.sleep(2)


def get_job_pod_name(name: str, namespace: str) -> Optional[str]:
    """
    Job이 생성한 Pod 이름을 하나 반환.
    """
    core = client.CoreV1Api()
    label_selector = f"job-name={name}"
    pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
    if pods.items:
        return pods.items[0].metadata.name
    return None


def get_pod_logs(pod: str, namespace: str, container: Optional[str] = None) -> str:
    """
    Pod 로그를 문자열로 반환.
    """
    core = client.CoreV1Api()
    return core.read_namespaced_pod_log(
        name=pod,
        namespace=namespace,
        container=container,
        follow=False,
        tail_lines=1000,
    )


def delete_job(name: str, namespace: str) -> None:
    """
    Job 및 하위 Pod 삭제.
    """
    batch = client.BatchV1Api()
    propagation = client.V1DeleteOptions(propagation_policy="Foreground")
    try:
        batch.delete_namespaced_job(name=name, namespace=namespace, body=propagation)
    except ApiException as e:
        if e.status != 404:
            raise
