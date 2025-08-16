#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 노드 상태, 버전, 런타임, taint/label, 조건을 점검한다.
# - apiserver /livez, /readyz 헬스엔드포인트를 확인한다.

ns() { echo "[check-nodes] $*"; }

# 현재 컨텍스트 출력
ns "kubectl context: $(kubectl config current-context || true)"
echo

# API 서버 헬스체크
ns "kube-apiserver livez:"
kubectl get --raw='/livez' 2>/dev/null | head -n 5 || ns "failed to GET /livez"
echo
ns "kube-apiserver readyz:"
kubectl get --raw='/readyz' 2>/dev/null | head -n 5 || ns "failed to GET /readyz"
echo

# 노드 목록 및 요약
ns "Nodes (wide):"
kubectl get nodes -o wide || { ns "failed to get nodes"; exit 1; }
echo

# 노드 상세: 버전, 런타임, taints, labels
for n in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
  echo "----- ${n} -----"
  ns "Version / Runtime:"
  kubectl get node "${n}" -o jsonpath='{.status.nodeInfo.kubeletVersion}{" / "}{.status.nodeInfo.containerRuntimeVersion}{"\n"}' || true
  echo

  ns "Taints:"
  kubectl get node "${n}" -o jsonpath='{range .spec.taints[*]}{.key}{"="}{.value}{":"}{.effect}{"\n"}{end}' || echo "(none)"
  echo

  ns "Labels (kata-related and roles):"
  kubectl get node "${n}" --show-labels | sed -n '2p' | tr ',' '\n' | egrep 'node-role|katacontainers\.io|beta\.kubernetes\.io|kubernetes\.io/hostname' || true
  echo

  ns "Conditions:"
  kubectl describe node "${n}" | sed -n '/Conditions:/,/Addresses:/p' || true
  echo
done
