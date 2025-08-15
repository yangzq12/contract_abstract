from web3 import Web3
import logging
from slither.tools.read_storage.read_storage import SlitherReadStorage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ContractInfo:
    def __init__(self, rpc_url, contracts=None):
        self.rpc_url = rpc_url
        # 连接到以太坊节点
        # 如果您有本地节点，可以使用：
        # w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
        # 或者连接到公共节点（例如 Infura，请替换 YOUR_INFURA_PROJECT_ID）
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        # # 或者连接到 Alchemy (请替换 YOUR_ALCHEMY_API_KEY)
        # w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/YOUR_ALCHEMY_API_KEY'))
        # 检查是否成功连接
        if w3.is_connected():
            logger.info("成功连接到以太坊节点")
        else:
            logger.error("无法连接到以太坊节点")
            raise Exception("无法连接到以太坊节点")
        self.w3 = w3
        self.read_storage = SlitherReadStorage(contracts, 20)


    def get_contract_bytecode(self, contract_address):
        
        # 确保地址格式正确
        contract_address = self.w3.to_checksum_address(contract_address)
        # 获取合约地址的字节码
        # 使用 eth.get_code 方法
        bytecode = self.w3.eth.get_code(contract_address)

        # 字节码会以 bytes 对象的形式返回，通常需要转换为十六进制字符串
        bytecode_hex = bytecode.hex()

        logger.info(f"合约地址: {contract_address}")
        logger.debug(f"字节码 (hex): {bytecode_hex}")

        return bytecode_hex


    def get_logic_contract_address(self, proxy_contract_address):
        # 根据proxy合约的标准获取真实的逻辑合约，目前只支持eip1967的proxy，逻辑合约在slot==0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
        # 获取代理合约的逻辑合约地址
        # 确保地址格式正确
        contract_address = self.w3.to_checksum_address(proxy_contract_address)
        # 使用 eth.get_storage_at 方法
        slot = int.to_bytes(int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",16),32,byteorder="big")
        logic_contract_address = bytes(self.w3.eth.get_storage_at(contract_address, slot)).rjust(32, bytes(1))
        logic_contract_address_value = self.read_storage.convert_value_to_type(logic_contract_address, 160, 0, "address")
        logic_contract_address_value = self.w3.to_checksum_address(logic_contract_address_value)

        logger.info(f"逻辑合约地址: {logic_contract_address_value}")

        return logic_contract_address_value

    