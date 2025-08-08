// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

/**
 * @title NodeRegistry
 * @dev 노드 제공자가 자신의 컴퓨팅 자원을 등록하고 관리하는 컨트랙트.
 */
contract NodeRegistry {
    // 1. 노드 정보를 담을 구조체
    struct Node {
        address owner;          // 노드 소유자 주소 (고유 ID)
        string location;        // 서버 위치 (예: "Seoul, KR")
        uint256 cpuUnits;       // CPU 코어 수
        uint256 ramMb;          // RAM 용량 (MB 단위)
        bool isAvailable;       // 현재 작업 가능한 상태인지 여부
    }

    // 2. 노드 소유자 주소와 노드 정보를 1:1로 매핑하여 저장
    mapping(address => Node) public nodes;

    // 3. 전체 노드 목록을 쉽게 조회하기 위한 주소 배열
    address[] public nodeList;

    /**
     * @dev 새로운 노드를 블록체인에 등록하는 함수.
     */
    function registerNode(
        string calldata _location,
        uint256 _cpu,
        uint256 _ram
    ) public {
        // 이미 등록된 노드는 중복 등록 방지
        require(nodes[msg.sender].owner == address(0), "Node already registered.");

        // 노드 정보 저장
        nodes[msg.sender] = Node(
            msg.sender,
            _location,
            _cpu,
            _ram,
            true // 처음 등록 시 기본적으로 '사용 가능' 상태
        );

        // 전체 노드 리스트에 주소 추가
        nodeList.push(msg.sender);
    }

    /**
     * @dev 등록된 모든 노드의 주소 리스트를 반환하는 읽기 전용 함수.
     */
    function getNodeList() public view returns (address[] memory) {
        return nodeList;
    }
}
