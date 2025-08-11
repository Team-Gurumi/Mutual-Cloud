// scripts/deploy.js
const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying NodeRegistry contract...");

  const Factory = await ethers.getContractFactory("NodeRegistry");

  // 가스추정 우회: 레거시 트랜잭션 + 0 가스 + 넉넉한 gasLimit
  const overrides = {
    type: 0,          // legacy tx
    gasPrice: 0n,     // Besu에서 0 허용
    gasLimit: 4_000_000n,
  };

  // 생성자 인자 없으면 overrides만, 있으면 (arg1, arg2, ..., overrides)
  const contract = await Factory.deploy(overrides);

  await contract.waitForDeployment();
  const addr = await contract.getAddress();
  console.log("NodeRegistry deployed to:", addr);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

