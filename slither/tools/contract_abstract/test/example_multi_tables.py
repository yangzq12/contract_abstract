#!/usr/bin/env python3
"""
多合约地址表管理示例
"""

from transaction_info import TransactionInfo

def main():
    """演示多合约地址表管理"""
    print("=== 多合约地址表管理示例 ===")
    
    # 配置
    ETHERSCAN_API_KEY = "your_etherscan_api_key_here"
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'ethereum_transactions',
        'user': 'postgres',
        'password': 'password',
        'port': 5432
    }
    
    # 多个合约地址
    contract_addresses = [
        "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",  # Aave V3 Pool
        "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
        "0xa0b86a33e6441b8c4c8c8c8c8c8c8c8c8c8c8c8"   # 示例地址
    ]
    
    # 为每个合约地址创建独立的TransactionInfo实例
    tx_instances = {}
    
    for address in contract_addresses:
        print(f"\n处理合约地址: {address}")
        
        # 创建实例
        tx_info = TransactionInfo(
            address=address,
            etherscan_api_key=ETHERSCAN_API_KEY,
            contract_info=None,  # 需要提供实际的contract_info对象
            db_config=DB_CONFIG
        )
        
        # 连接数据库并创建表
        tx_info.connect_db()
        tx_info.create_tables()
        
        # 显示表名
        print(f"创建的表名: {tx_info.table_name}")
        
        # 保存到字典中
        tx_instances[address] = tx_info
    
    # 示例：为不同合约保存不同的交易数据
    print("\n=== 保存示例数据 ===")
    
    # Aave V3 Pool 的交易数据
    aave_transaction = {
        'blockNumber': '23100743',
        'blockHash': '0xa0ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a04',
        'timeStamp': '1754709239',
        'hash': '0xbf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c096f',
        'nonce': '2318',
        'transactionIndex': '183',
        'from': '0x0a0ae914771ec0a5851049864ccc27b1baa8cd43',
        'to': '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2',
        'value': '0',
        'gas': '300000',
        'gasPrice': '282232339',
        'input': '0x573ade81000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec70000000000000000000000000000000000000000000000000000000708ea1b7800000000000000000000000000000000000000000000000000000000000000020000000000000000000000000a0ae914771ec0a5851049864ccc27b1baa8cd43',
        'methodId': '0x573ade81',
        'functionName': 'repay(address _owner, uint256 _pid, uint256 _amount, address _payer)',
        'contractAddress': '',
        'cumulativeGasUsed': '20184909',
        'txreceipt_status': '1',
        'gasUsed': '161175',
        'confirmations': '42276',
        'isError': '0'
    }
    
    # USDT 的交易数据
    usdt_transaction = {
        'blockNumber': '23100744',
        'blockHash': '0xb1ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a05',
        'timeStamp': '1754709240',
        'hash': '0xcf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c096e',
        'nonce': '2319',
        'transactionIndex': '184',
        'from': '0x1a1ae914771ec0a5851049864ccc27b1baa8cd44',
        'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
        'value': '1000000000000000000',
        'gas': '210000',
        'gasPrice': '20000000000',
        'input': '0x',
        'methodId': '0x',
        'functionName': 'transfer()',
        'contractAddress': '',
        'cumulativeGasUsed': '21000',
        'txreceipt_status': '1',
        'gasUsed': '21000',
        'confirmations': '42275',
        'isError': '0'
    }
    
    # 保存数据到对应的表
    print("保存 Aave V3 Pool 交易数据...")
    success1 = tx_instances[contract_addresses[0]].save_single_transaction(aave_transaction)
    print(f"保存结果: {success1}")
    
    print("保存 USDT 交易数据...")
    success2 = tx_instances[contract_addresses[1]].save_single_transaction(usdt_transaction)
    print(f"保存结果: {success2}")
    
    # 查询各表的数据
    print("\n=== 查询各表数据 ===")
    
    for address, tx_info in tx_instances.items():
        print(f"\n查询合约 {address} 的数据:")
        
        # 获取最新区块号
        latest_block = tx_info.get_latest_block_number()
        print(f"  最新区块号: {latest_block}")
        
        # 获取区块范围
        block_range = tx_info.get_block_range()
        if block_range:
            print(f"  区块范围: {block_range['min_block']} - {block_range['max_block']}")
        
        # 查询交易数据
        transactions = tx_info.get_transactions_from_db(limit=5)
        print(f"  交易数量: {len(transactions)}")
        
        # 关闭连接
        tx_info.close_db_connection()
    
    print("\n✅ 多合约地址表管理示例完成！")

if __name__ == "__main__":
    main()
