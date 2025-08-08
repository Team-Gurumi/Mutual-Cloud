// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

/**
 * @title JobMarketplace
 * @dev 사용자가 작업을 요청하고 오라클이 결과를 보고하는 시장 컨트랙트.
 */
contract JobMarketplace {
    // 1. 작업 정보를 담을 구조체
    struct Job {
        bytes32 jobId;          // 작업 고유 ID
        address requester;      // 작업을 요청한 사용자 주소
        address provider;       // 작업을 수행할 노드 제공자 주소
        string status;          // 작업 상태: "REQUESTED", "COMPLETED", "FAILED"
    }

    // 2. jobId와 작업 정보를 1:1로 매핑하여 저장
    mapping(bytes32 => Job) public jobs;

    // 3. 오라클이 감지할 이벤트들
    event ResourceRequested(bytes32 indexed jobId, address indexed provider);
    event JobCompleted(bytes32 indexed jobId, string finalStatus);

    /**
     * @dev 사용자가 특정 노드 제공자를 지정하여 작업을 요청하는 함수.
     */
    function requestComputation(address _provider) public {
        // 고유한 jobId 생성 (요청자 주소와 현재 시간을 조합하여 해시)
        bytes32 jobId = keccak256(abi.encodePacked(msg.sender, block.timestamp));

        // 작업 정보 생성 및 저장
        jobs[jobId] = Job(jobId, msg.sender, _provider, "REQUESTED");

        // 오라클에게 신호를 보내기 위해 이벤트 발생
        emit ResourceRequested(jobId, _provider);
    }

    /**
     * @dev 오라클이 작업 완료 후 결과를 보고하는 함수.
     */
    function finalizeJob(bytes32 _jobId, bool _wasSuccessful) public {
        // 참고: 실제 시스템에서는 이 함수를 오라클만 호출할 수 있도록
        // require(msg.sender == oracleAddress, "Not authorized"); 와 같은 접근 제어가 필요합니다.

        Job storage job = jobs[_jobId]; // 수정할 데이터를 storage로 가져옴
        require(job.requester != address(0), "Job does not exist.");

        // 성공/실패 여부에 따라 상태 업데이트
        if (_wasSuccessful) {
            job.status = "COMPLETED";
        } else {
            job.status = "FAILED";
        }

        // 최종 상태를 DApp이 알 수 있도록 이벤트 발생
        emit JobCompleted(_jobId, job.status);
    }
}
