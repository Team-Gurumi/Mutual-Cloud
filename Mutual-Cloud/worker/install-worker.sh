#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - Ubuntu 워커 노드에 containerd + Kata Containers + Kubernetes(kubelet/kubeadm/kubectl)를 설치한다.
# - 기본 런타임은 runc를 유지하고, Kata를 추가 런타임으로 등록한다.
# - 설치 후 control-plane의 join 명령으로 클러스터에 합류한다.
#
# 전제:
# - 루트 권한 필요(sudo).
# - control-plane에서 출력된 'kubeadm join ...' 명령을 확보해 둘 것.
#
# 사용법:
#   1) 환경변수로 제공
#       export KUBEADM_JOIN="kubeadm join <...>"
#       sudo ./install-worker.sh
#   2) 파일로 제공
#       cp worker/config/join.env.example worker/config/join.env
#       파일의 KUBEADM_JOIN 값을 실제 값으로 수정 후:
#       sudo ./install-worker.sh

K8S_VERSION_LINE="core:/stable:/v1.29"

log() { echo "[install-worker] $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    log "root 권한으로 실행해야 한다. sudo로 다시 실행할 것."
    exit 1
  fi
}

load_join_from_file_if_exists() {
  # worker/config/join.env 파일이 있으면 source
  local script_dir; script_dir="$(cd "$(dirname "$0")" && pwd)"
  local join_file="${script_dir}/config/join.env"
  if [[ -f "${join_file}" ]]; then
    # shellcheck disable=SC1090
    source "${join_file}"
  fi
}

require_join() {
  if [[ -z "${KUBEADM_JOIN:-}" ]]; then
    log "KUBEADM_JOIN 값이 비어 있다. 다음 중 한 가지 방식을 사용해 설정할 것:"
    log "1) export KUBEADM_JOIN=\"kubeadm join <...>\" 후 이 스크립트 실행"
    log "2) worker/config/join.env 파일을 생성하고 KUBEADM_JOIN 값을 채운 뒤 실행"
    exit 1
  fi
}

require_root
load_join_from_file_if_exists

log "1/6 의존 패키지 설치"
apt-get update -y
# ipset, iptables는 Calico 사용 시 유용하며, 최신 버전에는 대부분 포함되어 있지만 명시적으로 추가
apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common apt-transport-https ipset iptables

log "2/6 Kata Containers 설치"
. /etc/os-release
mkdir -p /etc/apt/keyrings # 키링 디렉토리 생성
# apt-key add 대신 gpg --dearmor 사용 (최신 권장 방식)
curl -fsSL "https://download.opensuse.org/repositories/home:/katacontainers:/releases:/${VERSION_ID}/xUbuntu_${VERSION_ID}/Release.key" | gpg --dearmor -o /etc/apt/keyrings/kata-containers-keyring.gpg
# signed-by 옵션으로 키 사용 명시
echo "deb [signed-by=/etc/apt/keyrings/kata-containers-keyring.gpg] http://download.opensuse.org/repositories/home:/katacontainers:/releases:/${VERSION_ID}/xUbuntu_${VERSION_ID}/ /" > /etc/apt/sources.list.d/kata-containers.list
apt-get update -y
apt-get install -y kata-containers

log "3/6 containerd 설치 및 설정"
apt-get install -y containerd
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml

# runc에서 systemd cgroup 사용 강제
# 이미 해당 라인이 있다면 sed가 중복 추가하지 않도록 조건을 추가
if ! grep -q 'SystemdCgroup = true' /etc/containerd/config.toml; then
  sed -i '/\[plugins\."io\.containerd\.grpc\.v1\.cri"\.containerd\.runtimes\.runc\.options\]/a \ \ SystemdCgroup = true' /etc/containerd/config.toml
fi

# kata 런타임 등록 (기본 런타임은 runc 유지)
if ! grep -q '\[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata\]' /etc/containerd/config.toml; then
  cat >>/etc/containerd/config.toml <<'EOF'

[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata]
  runtime_type = "io.containerd.kata.v2"
EOF
fi

systemctl enable --now containerd

log "4/6 Kubernetes 설치 (pkgs.k8s.io)"
mkdir -p /etc/apt/keyrings
curl -fsSL "https://pkgs.k8s.io/${K8S_VERSION_LINE}/deb/Release.key" | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/${K8S_VERSION_LINE}/deb/ /" > /etc/apt/sources.list.d/kubernetes.list
apt-get update -y
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

log "5/6 커널 모듈, sysctl, swap 비활성"
swapoff -a || true
sed -i '/ swap / s/^/#/' /etc/fstab || true
cat >/etc/modules-load.d/k8s.conf <<'EOF'
overlay
br_netfilter
EOF
modprobe overlay || true
modprobe br_netfilter || true
cat >/etc/sysctl.d/k8s.conf <<'EOF'
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
EOF
sysctl --system

log "6/6 클러스터 조인"
require_join
bash -c "${KUBEADM_JOIN}"

# 노드 라벨링은 컨트롤 플레인에서 실행하는 것이 일반적입니다.
# 워커 노드에서 kubectl 명령을 실행하려면 kubeconfig 파일이 필요하며,
# 이는 보안 및 관리 복잡성을 증가시킵니다.
# 따라서 이 부분은 제거하거나, 컨트롤 플레인에서 조인 후 실행하도록 안내하는 것이 좋습니다.
# NODE_NAME="$(hostname)"
# kubectl label node "${NODE_NAME}" katacontainers.io/kata-runtime=true --overwrite || true

log "설치 및 조인 완료"