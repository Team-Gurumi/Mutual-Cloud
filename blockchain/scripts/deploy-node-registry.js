// scripts/deploy-node-registry.js
const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying NodeRegistry...");
  const Factory = await ethers.getContractFactory("NodeRegistry");
  const c = await Factory.deploy();                 // 생성자 인자 없으면 비움
  await c.waitForDeployment();                      // ethers v6
  console.log("NodeRegistry deployed at:", await c.getAddress());
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

