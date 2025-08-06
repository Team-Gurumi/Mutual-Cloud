// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

contract P2PComputeMarket {
    enum JobStatus { Submitted, Assigned, Completed }

    struct Job {
        string inputHash;     // Hash of job.tgz
        string cid;           // IPFS CID
        address requester;    // 수요자 주소
        address provider;     // 공급자 주소
        string resultHash;    // Hash of result.tar.gz
        bytes signature;      // 공급자의 서명
        JobStatus status;
    }

    mapping(uint => Job) public jobs;
    uint public jobCount;

    event JobSubmitted(uint jobId, address requester, string inputHash, string cid);
    event JobAssigned(uint jobId, address provider);
    event JobCompleted(uint jobId, string resultHash);

    /// @notice 수요자가 연산 작업을 제출
    function submitJob(string calldata inputHash, string calldata cid) external returns (uint) {
        uint jobId = jobCount++;
        jobs[jobId] = Job({
            inputHash: inputHash,
            cid: cid,
            requester: msg.sender,
            provider: address(0),
            resultHash: "",
            signature: "",
            status: JobStatus.Submitted
        });
        emit JobSubmitted(jobId, msg.sender, inputHash, cid);
        return jobId;
    }

    /// @notice 공급자 할당
    function assign(uint jobId, address provider) external {
        Job storage job = jobs[jobId];
        require(job.requester == msg.sender, "Not authorized");
        require(job.status == JobStatus.Submitted, "Job not available");
        job.provider = provider;
        job.status = JobStatus.Assigned;
        emit JobAssigned(jobId, provider);
    }

    /// @notice 작업 완료 및 결과 제출
    function complete(uint jobId, string calldata resultHash, bytes calldata signature) external {
        Job storage job = jobs[jobId];
        require(msg.sender == job.provider, "Not provider");
        require(job.status == JobStatus.Assigned, "Job not assigned");
        job.resultHash = resultHash;
        job.signature = signature;
        job.status = JobStatus.Completed;
        emit JobCompleted(jobId, resultHash);
    }
}

