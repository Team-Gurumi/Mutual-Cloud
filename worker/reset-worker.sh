#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 워커 노드를 클러스터에서 분리하고 로컬 상태를 정리한다.
# - kubeadm reset, CNI/iptables 정리, 남은 디렉터리 정리까지 수행한다.
# 주의:
# - 데이터가 삭제된다. 다시 조인하려면 control-plane에서 새로운 join 토큰을 받아야 한다.

log() { echo "[reset-worker] $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    log "root 권한으로 실행해야 한다. sudo로 다시 실행할 것."
    exit 1
  fi
}

require_root

log "1/5 kubeadm reset"
# 워커는 로컬에서 reset만 수행해도 충분하다(클러스터 측 노드 객체는 control-plane에서 삭제 가능).
kubeadm reset -f || true
systemctl stop kubelet || true

log "2/5 CNI, iptables, 네트워크 인터페이스 정리"
rm -rf /etc/cni/net.d/* || true
rm -rf /var/lib/cni/* || true

ip link del cni0 2>/dev/null || true
ip link del flannel.1 2>/dev/null || true
for i in $(ip -o link show | awk -F': ' '{print $2}' | grep -E '^cali'); do
  ip link del "$i" 2>/dev/null || true
done

iptables -F || true
iptables -t nat -F || true
iptables -t mangle -F || true
iptables -X || true

log "3/5 디렉터리 정리"
rm -rf /etc/kubernetes || true
rm -rf /var/lib/etcd || true
rm -rf /var/lib/kubelet/pki || true
rm -rf /var/lib/kubelet/* || true
rm -rf /var/lib/containerd/io.containerd.runtime.v2.task/k8s.io || true

log "4/5 서비스 재시작"
systemctl restart containerd || true
systemctl restart kubelet || true

log "5/5 상태 요약"
echo "초기화 완료. 다시 조인하려면 control-plane에서 'kubeadm token create --print-join-command'로 새 토큰을 발급받아:"
echo "  export KUBEADM_JOIN=\"kubeadm join <...>\""
echo "  sudo ./install-worker.sh"
