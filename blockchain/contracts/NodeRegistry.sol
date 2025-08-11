// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title NodeRegistry
 * @dev 노드 제공자가 자신의 컴퓨팅 자원을 등록하고 관리하는 컨트랙트.
 */
contract NodeRegistry {
    struct Node {
        address owner;
        string location;
        uint256 cpuUnits;
        uint256 ramMb;
        bool isAvailable;
    }

    mapping(address => Node) public nodes;
    address[] public nodeList;

    function registerNode(
        string calldata _location,
        uint256 _cpu,
        uint256 _ram
    ) public {
        require(nodes[msg.sender].owner == address(0), "Node already registered.");
        nodes[msg.sender] = Node(
            msg.sender,
            _location,
            _cpu,
            _ram,
            true
        );
        nodeList.push(msg.sender);
    }

    function getNodeList() public view returns (address[] memory) {
        return nodeList;
    }
}
