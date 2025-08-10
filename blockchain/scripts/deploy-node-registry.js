const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying NodeRegistry...");
  const Factory = await ethers.getContractFactory("NodeRegistry");
  // 네트워크에서 gasPrice=0을 이미 강제했으므로 override 불필요
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  const addr = await contract.getAddress();
  console.log("NodeRegistry deployed at:", addr);
}

main().catch((e) => { console.error(e); process.exit(1); });
