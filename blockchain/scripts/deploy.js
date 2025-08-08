const hre = require("hardhat");

async function main() {
  console.log("Deploying NodeRegistry contract...");
  const NodeRegistry = await hre.ethers.getContractFactory("NodeRegistry");
  const nodeRegistry = await NodeRegistry.deploy();
  // .deployed() 함수는 더 이상 사용되지 않으므로 이 줄을 삭제하거나 주석 처리합니다.
  // await nodeRegistry.deployed(); 
  console.log(`✅ NodeRegistry deployed to: ${await nodeRegistry.getAddress()}`);

  console.log("Deploying JobMarketplace contract...");
  // 오류 메시지에 P2PComputeMarket.sol이 있었으므로, 실제 컨트랙트 이름으로 수정했습니다.
  // 만약 JobMarketplace가 맞다면 원래대로 되돌려주세요.
  const P2PComputeMarket = await hre.ethers.getContractFactory("P2PComputeMarket");
  const p2pComputeMarket = await P2PComputeMarket.deploy();
  // await p2pComputeMarket.deployed();
  console.log(`✅ P2PComputeMarket deployed to: ${await p2pComputeMarket.getAddress()}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
