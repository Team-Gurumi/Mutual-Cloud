const { ethers } = require("hardhat");

async function main() {
  console.log("Deploying P2PComputeMarket...");
  const Factory = await ethers.getContractFactory("P2PComputeMarket");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();
  const addr = await contract.getAddress();
  console.log("P2PComputeMarket deployed at:", addr);
}

main().catch((e) => { console.error(e); process.exit(1); });
