#!/usr/bin/env python3
# 목적:
# - Kata RuntimeClass를 사용하는 Job을 생성/실행하고, 완료까지 대기 후 로그를 수집한다.
# - 옵션으로 외부 YAML을 적용할 수도 있다.

import argparse
import sys
import yaml
from pathlib import Path

from utils import (
    load_kube,
    build_job_manifest,
    apply_yaml,
    create_job_from_manifest,
    wait_for_job_complete,
    get_job_pod_name,
    get_pod_logs,
    delete_job,
)

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(path: Path):
    if not path.exists():
        # 설정 파일이 없으면 빈 딕셔너리 반환 (오류가 아님)
        return {}
    with path.open("r", encoding="utf-8") as f:
        # yaml.safe_load는 파일이 비어있으면 None을 반환하므로, 빈 딕셔너리로 처리
        return yaml.safe_load(f) or {}


def parse_args():
    p = argparse.ArgumentParser(description="Mutual Cloud Requester")
    p.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="config.yaml 경로")
    p.add_argument("--namespace", type=str, help="K8s namespace")
    p.add_argument("--kubeconfig", type=str, help="KUBECONFIG 경로")
    p.add_argument("--name", type=str, required=False, help="Job 이름 (기본: 자동 생성)")
    p.add_argument("--yaml", type=str, help="외부 YAML을 그대로 apply하여 Job 실행")
    p.add_argument("--image", type=str, help="컨테이너 이미지")
    p.add_argument("--cmd", type=str, nargs="+", help="command 리스트")
    p.add_argument("--args", type=str, nargs="+", help="args 리스트")
    p.add_argument("--runtime-class", type=str, help="runtimeClassName (기본: kata)")
    p.add_argument("--cpu-request", type=str, help="예: 500m")
    p.add_argument("--cpu-limit", type=str, help="예: 1")
    p.add_argument("--mem-request", type=str, help="예: 512Mi")
    p.add_argument("--mem-limit", type=str, help="예: 1Gi")
    p.add_argument("--wait-timeout", type=int, help="완료 대기 타임아웃(초)")
    p.add_argument("--no-delete", action="store_true", help="완료 후 Job 삭제하지 않음")
    p.add_argument("--node-selector", type=str, nargs="+",
                   help='nodeSelector key=value 형태 여러 개 지정 가능. 예: katacontainers.io/kata-runtime=true')

    return p.parse_args()


def parse_node_selector(pairs):
    if not pairs:
        return None
    out = {}
    for kv in pairs:
        if "=" not in kv:
            raise ValueError(f"nodeSelector 항목은 key=value 형식이어야 함: {kv}")
        k, v = kv.split("=", 1)
        out[k] = v
    return out


def main():
    args = parse_args()
    cfg = load_config(Path(args.config))

    kubeconfig = args.kubeconfig or cfg.get("kubeconfig")
    namespace = args.namespace or cfg.get("namespace", "default")
    runtime_class = args.runtime_class or cfg.get("runtime_class", "kata")
    image = args.image or cfg.get("image", "ubuntu:20.04")
    command = args.cmd or cfg.get("command")
    cmd_args = args.args or cfg.get("args")
    cpu_request = args.cpu_request or cfg.get("cpu_request", "500m")
    cpu_limit = args.cpu_limit or cfg.get("cpu_limit", "1")
    mem_request = args.mem_request or cfg.get("mem_request", "512Mi")
    mem_limit = args.mem_limit or cfg.get("mem_limit", "1Gi")
    wait_timeout = args.wait_timeout or cfg.get("wait_timeout_seconds", 600)
    delete_after = cfg.get("delete_after", True) and not args.no_delete
    node_selector_pairs = args.node_selector if args.node_selector else cfg.get("node_selector") # config에서 node_selector 가져오기
    node_selector = parse_node_selector(node_selector_pairs) if node_selector_pairs else None

    # kube client 로드
    load_kube(kubeconfig)

    # 외부 YAML apply 모드
    if args.yaml:
        print(f"[requester] 외부 YAML 파일 '{args.yaml}' 적용 중...")
        try:
            created = apply_yaml(args.yaml, namespace=namespace)
            print(f"[requester] '{args.yaml}' 파일에서 {len(created)}개의 매니페스트를 적용했습니다.")
        except Exception as e:
            print(f"[requester] 외부 YAML 적용 중 오류 발생: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Job 이름
    name = args.name
    if not name:
        from datetime import datetime
        name = "kata-job-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")

    # Job 매니페스트 생성 및 제출 전에 필수 인자 확인
    if not image:
        print("[requester] 오류: 컨테이너 이미지(--image)가 지정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)
    if not command and not cmd_args:
        print("[requester] 경고: Job이 실행할 명령어(--cmd)나 인자(--args)가 지정되지 않았습니다. 컨테이너 이미지가 자체 엔트리포인트를 가지고 있지 않다면 Job이 즉시 완료되거나 예상대로 작동하지 않을 수 있습니다.", file=sys.stderr)

    # Job 매니페스트 생성 및 제출
    manifest = build_job_manifest(
        name=name,
        namespace=namespace,
        image=image,
        command=command,
        args=cmd_args,
        runtime_class=runtime_class,
        cpu_request=cpu_request,
        cpu_limit=cpu_limit,
        mem_request=mem_request,
        mem_limit=mem_limit,
        node_selector=node_selector,
    )
    print(f"[requester] Job '{namespace}/{name}' 생성을 시도합니다. 매니페스트: {yaml.dump(manifest, default_flow_style=False, sort_keys=False)}") # 디버깅을 위해 매니페스트 출력
    try:
        create_job_from_manifest(manifest)
        print(f"[requester] Job '{namespace}/{name}'이 성공적으로 생성되었습니다.")
    except Exception as e:
        print(f"[requester] Job 생성 중 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)

    # 완료 대기
    print(f"[requester] Job '{namespace}/{name}' 완료를 대기 중... (타임아웃: {wait_timeout}초)")
    try:
        status = wait_for_job_complete(name=name, namespace=namespace, timeout=wait_timeout)
        print(f"[requester] Job '{namespace}/{name}' 상태: {status}")
    except TimeoutError as e:
        print(f"[requester] 오류: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[requester] Job 대기 중 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)

    # 로그 수집
    print(f"[requester] Job '{namespace}/{name}'의 Pod 로그를 수집 중...")
    pod_name = get_job_pod_name(name=name, namespace=namespace)
    if pod_name:
        try:
            logs = get_pod_logs(pod=pod_name, namespace=namespace)
            print(f"----- Pod '{pod_name}' 로그 시작 -----")
            print(logs)
            print("----- Pod 로그 종료 -----")
        except Exception as e:
            print(f"[requester] Pod '{pod_name}' 로그 수집 중 오류 발생: {e}", file=sys.stderr)
    else:
        print("[requester] Job에 해당하는 Pod를 찾을 수 없습니다.", file=sys.stderr)

    # 정리
    if delete_after:
        print(f"[requester] 완료 후 Job '{namespace}/{name}' 삭제 중...")
        try:
            delete_job(name=name, namespace=namespace)
            print(f"[requester] Job '{namespace}/{name}'이 성공적으로 삭제되었습니다.")
        except Exception as e:
            print(f"[requester] Job 삭제 중 오류 발생 (이미 삭제되었을 수 있음): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()