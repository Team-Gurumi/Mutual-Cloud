#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 위 세 개의 점검 스크립트를 순차 실행한다.
# - 실행 권한이 없다면 부여한다.

root_dir="$(cd "$(dirname "$0")"/.. && pwd)"
verify_dir="${root_dir}/verify"

chmod +x "${verify_dir}/check-nodes.sh" "${verify_dir}/check-pods.sh" "${verify_dir}/check-network.sh" || true

"${verify_dir}/check-nodes.sh"
echo
"${verify_dir}/check-pods.sh"
echo
"${verify_dir}/check-network.sh"
echo

echo "[verify] all checks finished"
