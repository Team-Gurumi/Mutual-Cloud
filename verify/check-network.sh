#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - Calico CNI가 Pod 간 통신과 DNS를 제공하는지 확인한다.
# - busybox 파드 2개를 띄워 서로 ping, DNS 조회를 테스트한다.

nn() { echo "[check-network] $*"; }

# 테스트 파드 생성 함수
ensure_pod() {
  local name="$1"
  if ! kubectl get pod "${name}" >/dev/null 2>&1; then
    # RuntimeClass kata를 강제하지 않는다. CNI 동작 확인이 목적.
    kubectl run "${name}" --image=busybox --restart=Never --command -- sh -c "sleep 600" >/dev/null
  fi
}

ensure_pod netcheck-a
ensure_pod netcheck-b

nn "Waiting for pods to be Ready (timeout 120s)..."
kubectl wait --for=condition=Ready pod/netcheck-a --timeout=120s || true
kubectl wait --for=condition=Ready pod/netcheck-b --timeout=120s || true

IP_A=$(kubectl get pod netcheck-a -o jsonpath='{.status.podIP}' || true)
IP_B=$(kubectl get pod netcheck-b -o jsonpath='{.status.podIP}' || true)

echo "netcheck-a IP: ${IP_A}"
echo "netcheck-b IP: ${IP_B}"
echo

if [[ -n "${IP_A}" && -n "${IP_B}" ]]; then
  nn "Ping from A -> B (3 packets)"
  kubectl exec netcheck-a -- sh -c "ping -c 3 ${IP_B}" || true
  echo

  nn "Ping from B -> A (3 packets)"
  kubectl exec netcheck-b -- sh -c "ping -c 3 ${IP_A}" || true
  echo
else
  nn "Pod IPs not assigned; CNI may not be ready."
fi

nn "DNS resolution test from netcheck-a"
kubectl exec netcheck-a -- nslookup kubernetes.default.svc.cluster.local 2>/dev/null || true
echo

nn "HTTP to kube-dns ClusterIP (dig via busybox nslookup uses /etc/resolv.conf)"
kubectl get svc -n kube-system | egrep 'kube-dns|coredns' || true
echo

nn "Cleaning up test pods"
kubectl delete pod netcheck-a netcheck-b --ignore-not-found=true >/dev/null 2>&1 || true
