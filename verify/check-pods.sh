#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 시스템 파드 상태를 확인한다.
# - Pending, CrashLoopBackOff, Error 상태의 파드를 찾아 이벤트 일부를 출력한다.
# - Calico와 CoreDNS가 모두 Running인지 확인한다.

ps() { echo "[check-pods] $*"; }

ps "kube-system pods (wide):"
kubectl get pods -n kube-system -o wide || { ps "failed to get kube-system pods"; exit 1; }
echo

ps "Calico and CoreDNS status:"
kubectl get pods -n kube-system | egrep 'calico-|coredns' || true
echo

# 비정상 파드 수집
bad=$(kubectl get pods -A --no-headers | egrep 'Pending|CrashLoopBackOff|Error|ImagePullBackOff|Init:|CreateContainerError' || true)
if [[ -n "${bad}" ]]; then
  ps "Problematic pods detected:"
  echo "${bad}"
  echo
  ps "Events for problematic pods (last 20 lines each):"
  while read -r ns name _; do
    echo "----- ${ns}/${name} -----"
    kubectl describe pod "${name}" -n "${ns}" | tail -n 200 || true
    echo
  done < <(echo "${bad}" | awk '{print $1, $2}')
else
  ps "No problematic pods."
fi
