set -euo pipefail
cd ~/Mutual-Cloud/network

# 1) 4개 노드 주소 파일 없으면 생성
for i in 1 2 3 4; do
  if [ ! -f node-$i/data/node${i}Address ]; then
    besu --data-path=node-$i/data public-key export-address --to=node-$i/data/node${i}Address
  fi
done

# 2) 주소 로드(줄바꿈 제거) + 형식 검증
ADDR1=$(tr -d '\n' < node-1/data/node1Address)
ADDR2=$(tr -d '\n' < node-2/data/node2Address)
ADDR3=$(tr -d '\n' < node-3/data/node3Address)
ADDR4=$(tr -d '\n' < node-4/data/node4Address)
printf '%s\n' "$ADDR1" "$ADDR2" "$ADDR3" "$ADDR4" | grep -Eq '^(0x)[0-9a-fA-F]{40}$' || { echo "주소 형식 오류"; exit 1; }

# 3) ibftConfigFile.json 안전하게 생성(jq 사용)
jq -n \
  --arg a1 "$ADDR1" --arg a2 "$ADDR2" --arg a3 "$ADDR3" --arg a4 "$ADDR4" '
{
  genesis: {
    config: {
      chainId: 2025,
      berlinBlock: 0,
      londonBlock: 0,
      parisBlock: 0,
      shanghaiBlock: 0,
      cancunBlock: 0,
      ibft2: {
        blockperiodseconds: 2,
        epochlength: 30000,
        requesttimeoutseconds: 10,
        validators: [$a1, $a2, $a3, $a4]
      }
    },
    nonce: "0x0",
    timestamp: "0x0",
    gasLimit: "0x1fffffffffffff",
    difficulty: "0x1",
    mixHash: "0x0000000000000000000000000000000000000000000000000000000000000000",
    coinbase: "0x0000000000000000000000000000000000000000",
    baseFeePerGas: "0x0",
    alloc: {}
  },
  blockchain: { nodes: { generate: false } }
}' > ibftConfigFile.json

# 4) genesis.json 생성
rm -rf networkFiles
besu operator generate-blockchain-config --config-file=ibftConfigFile.json --to=networkFiles
cp networkFiles/genesis.json ./genesis.json

# 5) extraData 길이 확인(200+가 정상)
LEN=$(jq -r '.extraData' genesis.json | wc -c)
echo "extraData_len=$LEN"
[ "$LEN" -ge 200 ] || { echo "extraData 짧음(잘못된 genesis). 중단."; exit 1; }

# 6) 노드 DB 초기화(키 보존) + 새 genesis 배포
pkill -f besu 2>/dev/null || true
for i in 1 2 3 4; do
  mv node-$i/data/key node-$i/key.bak
  rm -rf node-$i/data/*
  mkdir -p node-$i/data
  mv node-$i/key.bak node-$i/data/key
  cp genesis.json node-$i/data/
done

# 7) 부트노드 enode 추출
PUB1=$(besu --data-path=node-1/data public-key export --to=- | tr -d '\n' | sed -E 's/^.*0x([0-9a-fA-F]{128}).*$/\1/')
ENODE1="enode://${PUB1}@127.0.0.1:30303"
echo "BOOTNODE=$ENODE1"

# 8) 4노드 기동
besu --data-path=node-1/data --genesis-file=genesis.json \
  --rpc-http-enabled --rpc-http-api=ETH,NET,WEB3,IBFT,ADMIN \
  --rpc-http-port=8545 --p2p-port=30303 &

besu --data-path=node-2/data --genesis-file=genesis.json \
  --rpc-http-enabled --rpc-http-port=8546 --p2p-port=30304 \
  --bootnodes="$ENODE1" &

besu --data-path=node-3/data --genesis-file=genesis.json \
  --rpc-http-enabled --rpc-http-port=8547 --p2p-port=30305 \
  --bootnodes="$ENODE1" &

besu --data-path=node-4/data --genesis-file=genesis.json \
  --rpc-http-enabled --rpc-http-port=8548 --p2p-port=30306 \
  --bootnodes="$ENODE1" &
