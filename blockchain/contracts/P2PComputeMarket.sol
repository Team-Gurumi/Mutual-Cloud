// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title P2PComputeMarket
 * @dev 사용자가 작업을 요청하고 오라클이 결과를 보고하는 시장 컨트랙트.
 */
contract P2PComputeMarket {
    struct Job {
        bytes32 jobId;
        address requester;
        address provider;
        string status; // "REQUESTED", "COMPLETED", "FAILED"
    }

    mapping(bytes32 => Job) public jobs;

    event ResourceRequested(bytes32 indexed jobId, address indexed provider);
    event JobCompleted(bytes32 indexed jobId, string finalStatus);

    function requestComputation(address _provider) public {
        bytes32 jobId = keccak256(abi.encodePacked(msg.sender, block.timestamp));
        jobs[jobId] = Job(jobId, msg.sender, _provider, "REQUESTED");
        emit ResourceRequested(jobId, _provider);
    }

    function finalizeJob(bytes32 _jobId, bool _wasSuccessful) public {
        Job storage job = jobs[_jobId];
        require(job.requester != address(0), "Job does not exist.");

        if (_wasSuccessful) {
            job.status = "COMPLETED";
        } else {
            job.status = "FAILED";
        }

        emit JobCompleted(_jobId, job.status);
    }
}
