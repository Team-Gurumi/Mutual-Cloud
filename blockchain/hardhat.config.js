require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.28", // 또는 자신의 컨트랙트 버전
  networks: {
    besu_poa: {
      // 1. url에 Besu 서버의 테일스케일 IP를 입력합니다.
      url: "http://100.119.53.94:8545",
   chainId: 2025,   
      // 2. accounts 배열에 Besu 노드의 개인키를 '0x'를 붙여서 넣습니다.
      accounts: ["0xa93ccaa9f53edca0247f3cab3d9554d0055677770b2aeced507656a1b8a5bff2"],
 gasPrice: 0,
    },
  },
};
