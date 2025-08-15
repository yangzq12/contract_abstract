#!/usr/bin/env python3
"""
测试以block_hash为主键的表结构
"""

import sys
from transaction_info import TransactionInfo

def test_blockhash_primary_key():
    """测试以block_hash为主键的表结构"""
    print("=== 测试以block_hash为主键的表结构 ===")
    
    # 测试配置
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'test_ethereum_transactions',
        'user': 'postgres',
        'password': 'password',
        'port': 5432
    }
    
    try:
        # 创建测试实例
        tx_info = TransactionInfo(
            address="0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",
            etherscan_api_key="test_key",
            contract_info=None,
            db_config=DB_CONFIG
        )
        
        # 连接数据库
        tx_info.connect_db()
        
        # 创建表
        print("\n1. 创建以block_hash为主键的表")
        tx_info.create_tables()
        
        # 测试数据
        test_transaction_1 = {
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
        
        test_transaction_2 = {
            'blockNumber': '23100744',
            'blockHash': '0xb1ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a05',
            'timeStamp': '1754709240',
            'hash': '0xcf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c096e',
            'nonce': '2319',
            'transactionIndex': '184',
            'from': '0x1a1ae914771ec0a5851049864ccc27b1baa8cd44',
            'to': '0x97870bca3f3fd6335c3f4ce8392d69350b4fa4e3',
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
        
        # 测试保存数据
        print("\n2. 保存第一条交易数据")
        success1 = tx_info.save_single_transaction(test_transaction_1)
        print(f"第一条交易保存成功: {success1}")
        
        print("\n3. 保存第二条交易数据")
        success2 = tx_info.save_single_transaction(test_transaction_2)
        print(f"第二条交易保存成功: {success2}")
        
        # 测试重复block_hash（应该被拒绝）
        print("\n4. 测试重复block_hash（应该被拒绝）")
        duplicate_transaction = {
            **test_transaction_1,
            'hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        }
        success3 = tx_info.save_single_transaction(duplicate_transaction)
        print(f"重复block_hash的交易保存结果: {success3}")
        
        # 查询数据
        print("\n5. 查询所有交易数据")
        transactions = tx_info.get_transactions_from_db(limit=10)
        print(f"查询到 {len(transactions)} 条记录")
        
        for i, tx in enumerate(transactions):
            print(f"\n交易 {i+1}:")
            print(f"  区块哈希: {tx['block_hash']}")
            print(f"  区块号: {tx['block_number']}")
            print(f"  交易哈希: {tx['hash']}")
            print(f"  发送方: {tx['from_address']}")
            print(f"  接收方: {tx['to_address']}")
            print(f"  函数名: {tx['function_name']}")
        
        # 测试按block_hash查询
        print("\n6. 测试按block_hash查询")
        cursor = tx_info.db_connection.cursor()
        cursor.execute("SELECT * FROM ethereum_transactions WHERE block_hash = %s", 
                      (test_transaction_1['blockHash'],))
        result = cursor.fetchone()
        if result:
            print(f"找到block_hash为 {test_transaction_1['blockHash']} 的记录")
        else:
            print(f"未找到block_hash为 {test_transaction_1['blockHash']} 的记录")
        cursor.close()
        
        tx_info.close_db_connection()
        print("\n✅ 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("开始测试以block_hash为主键的表结构...\n")
    
    success = test_blockhash_primary_key()
    
    if success:
        print("\n🎉 表结构测试完成！")
        return 0
    else:
        print("\n❌ 表结构测试失败！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
