#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 컨트롤플레인 노드를 초기 상태로 되돌린다.
# - kubeadm reset, CNI/iptables 정리, 남은 디렉터리 정리까지 수행한다.
# 주의:
# - 데이터가 삭제된다. etcd 데이터와 클러스터 설정이 모두 지워진다.

log() { echo "[reset-control-plane] $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    log "root 권한으로 실행해야 한다. sudo로 다시 실행할 것."
    exit 1
  fi
}

require_root

log "1/6 kubeadm reset"
kubeadm reset -f || true
systemctl stop kubelet || true

log "2/6 CNI, iptables, 네트워크 인터페이스 정리"
# CNI 디렉터리
rm -rf /etc/cni/net.d/* || true
rm -rf /var/lib/cni/* || true

# Calico 인터페이스/브리지 제거 시도
ip link del cni0 2>/dev/null || true
ip link del flannel.1 2>/dev/null || true
# cali* 인터페이스는 다수일 수 있으므로 루프 처리
for i in $(ip -o link show | awk -F': ' '{print $2}' | grep -E '^cali'); do
  ip link del "$i" 2>/dev/null || true
done

# iptables 규칙 초기화
iptables -F || true
iptables -t nat -F || true
iptables -t mangle -F || true
iptables -X || true

log "3/6 디렉터리 정리"
rm -rf /etc/kubernetes || true
rm -rf /var/lib/etcd || true
rm -rf /var/lib/kubelet/pki || true
rm -rf /var/lib/kubelet/* || true
rm -rf /var/lib/containerd/io.containerd.runtime.v2.task/k8s.io || true

log "4/6 containerd, kubelet 재시작"
systemctl restart containerd || true
systemctl restart kubelet || true

log "5/6 kubeconfig 정리"
KUBE_USER="${SUDO_USER:-root}"
rm -f /home/${KUBE_USER}/.kube/config || true

log "6/6 상태 요약"
echo "초기화 완료. 필요 시 다음 스크립트를 다시 실행하여 재설치:"
echo "controlplane/install-control-plane.sh"
