#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - Ubuntu 호스트에 containerd + Kata Containers + Kubernetes(Control-plane) + Calico를 설치한다.
# - 기본 런타임은 runc를 유지하고, Kata는 RuntimeClass로 선택적으로 사용한다.
# - Calico CIDR은 10.244.0.0/16으로 맞춘다.
#
# 전제:
# - 루트 권한 필요. (sudo로 실행)
# - 인터넷 통신 가능.
#
# 선택 환경변수:
# - APISERVER_ADVERTISE_ADDRESS: kube-apiserver advertise IP를 고정하고 싶을 때 지정.

K8S_VERSION_LINE="core:/stable:/v1.29"   # pkgs.k8s.io 채널
POD_CIDR="10.244.0.0/16"
CALICO_VERSION="v3.28.1"

APISERVER_ADVERTISE_ADDRESS="${APISERVER_ADVERTISE_ADDRESS:-}"

log() { echo "[install-control-plane] $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    log "root 권한으로 실행해야 한다. sudo로 다시 실행할 것."
    exit 1
  fi
}

require_root

log "1/9 의존 패키지 설치"
apt-get update -y
# ipset, iptables는 Calico 사용 시 유용하며, 최신 버전에는 대부분 포함되어 있지만 명시적으로 추가
apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common apt-transport-https ipset iptables

log "2/9 Kata Containers 설치"
. /etc/os-release
mkdir -p /etc/apt/keyrings # 키링 디렉토리 생성
curl -fsSL "https://download.opensuse.org/repositories/home:/katacontainers:/releases:/${VERSION_ID}/xUbuntu_${VERSION_ID}/Release.key" | gpg --dearmor -o /etc/apt/keyrings/kata-containers-keyring.gpg
# https://download.opensuse.org/repositories/home:/katacontainers:/releases:/20.04/xUbuntu_20.04/Release.key
echo "deb [signed-by=/etc/apt/keyrings/kata-containers-keyring.gpg] http://download.opensuse.org/repositories/home:/katacontainers:/releases:/${VERSION_ID}/xUbuntu_${VERSION_ID}/ /" > /etc/apt/sources.list.d/kata-containers.list
apt-get update -y
apt-get install -y kata-containers

log "3/9 containerd 설치 및 설정"
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

log "4/9 crictl 설정"
mkdir -p /etc/crictl
cat >/etc/crictl/config.yaml <<'EOF'
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
debug: false
EOF

log "5/9 Kubernetes 설치 (pkgs.k8s.io)"
mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/${K8S_VERSION_LINE}/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
# https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/${K8S_VERSION_LINE}/deb/ /" > /etc/apt/sources.list.d/kubernetes.list
apt-get update -y
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

log "6/9 커널 모듈, sysctl, swap 비활성"
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

log "7/9 kubeadm init 실행"
KUBEADM_ARGS=("--pod-network-cidr=${POD_CIDR}" "--cri-socket=unix:///run/containerd/containerd.sock")
if [[ -n "${APISERVER_ADVERTISE_ADDRESS}" ]]; then
  KUBEADM_ARGS+=("--apiserver-advertise-address=${APISERVER_ADVERTISE_ADDRESS}")
fi
kubeadm init "${KUBEADM_ARGS[@]}"

log "8/9 kubectl kubeconfig 배치"
KUBE_USER="${SUDO_USER:-root}"
mkdir -p /home/${KUBE_USER}/.kube
cp -i /etc/kubernetes/admin.conf /home/${KUBE_USER}/.kube/config
chown "$(id -u ${KUBE_USER}):$(id -g ${KUBE_USER})" /home/${KUBE_USER}/.kube/config

log "9/9 Calico 설치 및 RuntimeClass 적용"
workdir="$(mktemp -d)"
cd "${workdir}"
curl -fsSLO "https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/calico.yaml"
# https://raw.githubusercontent.com/projectcalico/calico/v3.28.1/manifests/calico.yaml
# 기본 192.168.0.0/16을 10.244.0.0/16으로 교체
sed -i 's/192.168.0.0\/16/10.244.0.0\/16/' calico.yaml
kubectl apply -f calico.yaml

# RuntimeClass는 repo의 controlplane/config/runtimeclass-kata.yaml이 있으면 사용, 없으면 임시 생성
if [[ -f "$(cd "$(dirname "$0")" && pwd)/config/runtimeclass-kata.yaml" ]]; then
  kubectl apply -f "$(cd "$(dirname "$0")" && pwd)/config/runtimeclass-kata.yaml"
else
  cat <<'EOF' | kubectl apply -f -
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata
handler: kata
EOF
fi

# 단일 노드 실험 시 컨트롤플레인 taint 해제 안내
echo "단일 노드 실험 시 다음을 실행하여 스케줄링 가능하게 할 수 있다:"
echo "kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true"

# kata 라벨 부여
NODE_NAME="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
kubectl label node "${NODE_NAME}" katacontainers.io/kata-runtime=true --overwrite

# 워커 조인을 위한 join 명령 출력
kubeadm token create --print-join-command || true

log "설치 완료"