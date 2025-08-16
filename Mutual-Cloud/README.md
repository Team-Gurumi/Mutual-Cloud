# Mutual-Cloud

## Overview
This repository bootstraps a Kubernetes host (Ubuntu) to run Kata Containers workloads. It provides:
- `install-control-plane.sh`: sets up a single-node control-plane with containerd, Kata, Calico CNI, and a `RuntimeClass` named `kata`.
- `install-worker.sh`: prepares a worker node (containerd+Kata) and joins it to the cluster.

> Notes
> - Default container runtime remains **runc** for core control-plane pods. Kata is opt-in via `runtimeClassName: kata`.
> - Pod CIDR defaults to `10.244.0.0/16` and Calico is configured to match.
> - Tested against Kubernetes 1.29 packages (pkgs.k8s.io) and Calico v3.28.1.

## Quickstart

### Control-plane (on the first server)
```bash
# clone and run
git clone https://github.com/<YOUR_GH_USERNAME>/kata-setup.git
cd kata-setup

# optionally set advertise IP if you want to pin the API server address
export APISERVER_ADVERTISE_ADDRESS=<HOST_IP>

bash install-control-plane.sh
```
This will print a `kubeadm join ...` command at the end. Save it for workers.

### Worker (on each supplier node)
```bash
# on each worker node
git clone https://github.com/<YOUR_GH_USERNAME>/kata-setup.git
cd kata-setup

# paste the exact join command you got from the control-plane
export KUBEADM_JOIN="kubeadm join <CP_IP>:6443 --token <...> --discovery-token-ca-cert-hash sha256:<...>"

bash install-worker.sh
```

### Verify
```bash
# on the control-plane
kubectl get nodes -o wide
kubectl get pods -n kube-system
kubectl get runtimeclass
```
You should see Calico pods running and a RuntimeClass named `kata`.