require("dotenv").config();
require("@nomicfoundation/hardhat-ethers");

const PK = process.env.PRIVATE_KEY;
const RPC = process.env.BESU_RPC || "http://127.0.0.1:8545";

// 선택: 키 형식 보정 (0x 없을 때 자동으로 붙이기)
const PRIVATE_KEY = PK && (PK.startsWith("0x") ? PK : `0x${PK}`);

module.exports = {
  solidity: "0.8.28",
  networks: {
    besu_poa: {
      url: RPC,
      chainId: 2025,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],  // ← 비어있으면 HH8 뜸
      gasPrice: 0                                   // 베수 min-gas-price=0이면 편함
    }
  }
};

