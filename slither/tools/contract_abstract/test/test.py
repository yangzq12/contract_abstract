import requests
from web3 import Web3

ETHERSCAN_API_KEY = "E8MPYVHVRQ73BTZANCW6FSGE2JH56PNY6J"
CONTRACT_ADDRESS = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
BLOCK_NUMBER = 	23100743  # 你要查询的区块

BASE_URL = "https://api.etherscan.io/api"

w3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/46b4ffa92d6348c299aaa345800ed333"))

def get_contract_abi(address):
    params = {
        "module": "contract",
        "action": "getabi",
        "address": address,
        "apikey": ETHERSCAN_API_KEY
    }
    resp = requests.get(BASE_URL, params=params).json()
    abi_json = resp.get("result")
    if abi_json and abi_json != 'Contract source code not verified':
        return w3.codec.decode_abi if abi_json is None else abi_json
    else:
        raise Exception("ABI not available or contract not verified on Etherscan")

def get_transactions(address, block, action):
    params = {
        "module": "account",
        "action": action,
        "address": address,
        "startblock": block,
        "endblock": block,
        "sort": "asc",
        "apikey": ETHERSCAN_API_KEY
    }
    resp = requests.get(BASE_URL, params=params).json()
    return resp.get("result", [])

def decode_input(abi, tx_input):
    contract = w3.eth.contract(abi=abi)
    try:
        func_obj, params = contract.decode_function_input(tx_input)
        return func_obj.fn_name, params
    except Exception:
        return None, None

def main():
    print("Fetching ABI from Etherscan...")
    abi_json = get_contract_abi("0x97287a4f35e583d924f78ad88db8afce1379189a")
    abi = None
    if isinstance(abi_json, str):
        import json
        abi = json.loads(abi_json)
    else:
        abi = abi_json

    print(f"Fetching normal transactions to {CONTRACT_ADDRESS} in block {BLOCK_NUMBER}...")
    normal_txs = get_transactions(CONTRACT_ADDRESS, BLOCK_NUMBER, "txlist")

    print(f"Fetching internal transactions to {CONTRACT_ADDRESS} in block {BLOCK_NUMBER}...")
    internal_txs = get_transactions(CONTRACT_ADDRESS, BLOCK_NUMBER, "txlistinternal")

    print("\n=== Normal Transactions ===")
    for tx in normal_txs:
        print(f"TxHash: {tx['hash']}")
        print(f"From: {tx['from']} -> To: {tx['to']}")
        if tx['input'] and tx['input'] != '0x':
            func_name, params = decode_input(abi, tx['input'])
            print(f"Function: {func_name}")
            print(f"Params: {params}")
        else:
            print("No input data or not a contract call")
        print()

    print("\n=== Internal Transactions ===")
    for tx in internal_txs:
        print(f"TxHash: {tx['hash']}")
        print(f"From: {tx['from']} -> To: {tx['to']}")
        if tx.get('input') and tx['input'] != '0x':
            func_name, params = decode_input(abi, tx['input'])
            print(f"Function: {func_name}")
            print(f"Params: {params}")
        else:
            print("No input data or not a contract call")
        print()

if __name__ == "__main__":
    main()
