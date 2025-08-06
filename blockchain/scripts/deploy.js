const hre = require("hardhat");

async function main() {
  const Market = await hre.ethers.getContractFactory("P2PComputeMarket");
  const contract = await Market.deploy();
    await contract.waitForDeployment(); // ethers v6 스타일
  console.log(`Contract deployed to: ${await contract.getAddress()}`);
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
