#!/usr/bin/env python3
"""
测试获取最新区块号功能
"""

import sys
from transaction_info import TransactionInfo

def test_latest_block_functions():
    """测试获取最新区块号的相关功能"""
    print("=== 测试获取最新区块号功能 ===")
    
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
        print("\n1. 创建表")
        tx_info.create_tables()
        
        # 测试空数据库
        print("\n2. 测试空数据库")
        latest_block = tx_info.get_latest_block_number()
        print(f"最新区块号: {latest_block}")
        
        latest_info = tx_info.get_latest_block_info()
        print(f"最新区块信息: {latest_info}")
        
        block_range = tx_info.get_block_range()
        print(f"区块范围: {block_range}")
        
        # 添加测试数据
        print("\n3. 添加测试数据")
        test_transactions = [
            {
                'blockNumber': '23100740',
                'blockHash': '0xa0ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a01',
                'timeStamp': '1754709236',
                'hash': '0xbf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c0961',
                'nonce': '2315',
                'transactionIndex': '180',
                'from': '0x0a0ae914771ec0a5851049864ccc27b1baa8cd40',
                'to': '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e0',
                'value': '0',
                'gas': '300000',
                'gasPrice': '282232339',
                'input': '0x',
                'methodId': '0x',
                'functionName': 'transfer()',
                'contractAddress': '',
                'cumulativeGasUsed': '20184900',
                'txreceipt_status': '1',
                'gasUsed': '161170',
                'confirmations': '42280',
                'isError': '0'
            },
            {
                'blockNumber': '23100742',
                'blockHash': '0xa0ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a03',
                'timeStamp': '1754709238',
                'hash': '0xbf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c0963',
                'nonce': '2317',
                'transactionIndex': '182',
                'from': '0x0a0ae914771ec0a5851049864ccc27b1baa8cd42',
                'to': '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2',
                'value': '0',
                'gas': '300000',
                'gasPrice': '282232339',
                'input': '0x',
                'methodId': '0x',
                'functionName': 'transfer()',
                'contractAddress': '',
                'cumulativeGasUsed': '20184907',
                'txreceipt_status': '1',
                'gasUsed': '161173',
                'confirmations': '42278',
                'isError': '0'
            },
            {
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
            },
            {
                'blockNumber': '23100745',
                'blockHash': '0xa0ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a06',
                'timeStamp': '1754709241',
                'hash': '0xbf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c096a',
                'nonce': '2320',
                'transactionIndex': '185',
                'from': '0x0a0ae914771ec0a5851049864ccc27b1baa8cd45',
                'to': '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e5',
                'value': '0',
                'gas': '300000',
                'gasPrice': '282232339',
                'input': '0x',
                'methodId': '0x',
                'functionName': 'transfer()',
                'contractAddress': '',
                'cumulativeGasUsed': '20184910',
                'txreceipt_status': '1',
                'gasUsed': '161176',
                'confirmations': '42274',
                'isError': '0'
            }
        ]
        
        saved_count = tx_info.save_transactions_to_db(test_transactions)
        print(f"保存了 {saved_count} 条交易记录")
        
        # 测试获取最新区块号
        print("\n4. 测试获取最新区块号")
        latest_block = tx_info.get_latest_block_number()
        print(f"最新区块号: {latest_block}")
        
        # 测试获取最新区块信息
        print("\n5. 测试获取最新区块信息")
        latest_info = tx_info.get_latest_block_info()
        if latest_info:
            print(f"最新区块信息:")
            for key, value in latest_info.items():
                print(f"  {key}: {value}")
        
        # 测试获取区块范围
        print("\n6. 测试获取区块范围")
        block_range = tx_info.get_block_range()
        if block_range:
            print(f"区块范围信息:")
            for key, value in block_range.items():
                print(f"  {key}: {value}")
        
        # 测试按区块号查询
        print("\n7. 测试按区块号查询")
        if latest_block:
            transactions = tx_info.get_transactions_from_db(
                start_block=latest_block,
                end_block=latest_block
            )
            print(f"最新区块 {latest_block} 包含 {len(transactions)} 笔交易")
        
        tx_info.close_db_connection()
        print("\n✅ 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("开始测试获取最新区块号功能...\n")
    
    success = test_latest_block_functions()
    
    if success:
        print("\n🎉 最新区块号功能测试完成！")
        return 0
    else:
        print("\n❌ 最新区块号功能测试失败！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
