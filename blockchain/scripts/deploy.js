const hre = require("hardhat");

async function main() {
  console.log("Deploying NodeRegistry contract...");
  const NodeRegistry = await hre.ethers.getContractFactory("NodeRegistry");
  const nodeRegistry = await NodeRegistry.deploy();
  await nodeRegistry.deployed();
  console.log(`✅ NodeRegistry deployed to: ${nodeRegistry.address}`);

  console.log("Deploying JobMarketplace contract...");
  const JobMarketplace = await hre.ethers.getContractFactory("JobMarketplace");
  const jobMarketplace = await JobMarketplace.deploy();
  await jobMarketplace.deployed();
  console.log(`✅ JobMarketplace deployed to: ${jobMarketplace.address}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
