require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.28", // 또는 자신의 컨트랙트 버전
  networks: {
    // 'networks' 객체 안에 'ganache_server'가 있어야 합니다.
    ganache_server: {
      // url에 Ganache 서버의 테일스케일 IP를 입력합니다.
      url: "http://100.119.53.94:8545",
      // accounts 배열에, Ganache가 출력해 준 개인키 중 하나를 '0x'를 붙여서 넣습니다.
      accounts: ["0xb62fe0d6eb191310b4cf57856ca344690654bc18c328cd0490f75f9789201a65"]
    }
  }
};
