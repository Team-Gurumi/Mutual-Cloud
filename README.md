# Mutual-Cloud

📂 프로젝트 구조

network/

    기능: 로컬 또는 프라이빗 네트워크 환경 설정.

    내용:

        besu 관련 설정: Hyperledger Besu 기반 노드 실행 스크립트, 네트워크 설정 파일.

        **제네시스 블록(genesis.json)**과 노드 키, IBFT(Proof of Authority) 합의 관련 설정.

        Docker 또는 systemd로 노드를 실행할 수 있는 구성.

    용도:

        프라이빗 블록체인 네트워크를 생성 및 유지.

        팀원들이 동일한 네트워크 환경에서 개발 가능하도록 함.

blockchain/

    기능: 스마트 컨트랙트 코드와 배포 스크립트 관리.

    내용:

        contracts/: Solidity로 작성된 스마트 컨트랙트 파일.

            NodeRegistry.sol: 노드 등록/조회 기능.

            P2PComputeMarket.sol: 작업 요청/완료 상태 관리.

        scripts/: Hardhat 배포 스크립트 (deploy-node-registry.js, deploy-market.js).

        hardhat.config.js: 네트워크 및 컴파일러 버전, 계정 설정.

        .env: 배포 시 필요한 개인키, RPC 주소 등 환경변수 저장.

    용도:

        스마트 컨트랙트를 컴파일하고, Besu 네트워크에 배포.

        배포된 주소를 다른 서비스와 연동.

