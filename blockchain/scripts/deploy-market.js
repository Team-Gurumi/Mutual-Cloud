// scripts/deploy-market.js
const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying P2PComputeMarket...");
  const Factory = await ethers.getContractFactory("P2PComputeMarket");
  const c = await Factory.deploy();                 // 생성자 인자 없으면 비움
  await c.waitForDeployment();
  console.log("P2PComputeMarket deployed at:", await c.getAddress());
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

