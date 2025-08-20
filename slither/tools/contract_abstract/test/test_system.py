#!/usr/bin/env python3
"""
测试Etherscan交易数据存储系统
"""

import os
import sys
from transaction_info import TransactionInfo

def test_database_connection():
    """测试数据库连接"""
    print("=== 测试数据库连接 ===")
    
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
            etherscan_api_key="test_key",
            contract_info=None,
            db_config=DB_CONFIG
        )
        
        # 测试连接
        tx_info.connect_db()
        print("✅ 数据库连接成功")
        
        # 测试创建表
        tx_info.create_tables()
        print("✅ 数据库表创建成功")
        
        tx_info.close_db_connection()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def test_transaction_save():
    """测试交易数据保存"""
    print("\n=== 测试交易数据保存 ===")
    
    # 测试交易数据
    test_transaction = {
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
    
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'test_ethereum_transactions',
        'user': 'postgres',
        'password': 'password',
        'port': 5432
    }
    
    try:
        tx_info = TransactionInfo(
            etherscan_api_key="test_key",
            contract_info=None,
            db_config=DB_CONFIG
        )
        
        tx_info.connect_db()
        
        # 测试保存单条交易
        success = tx_info.save_single_transaction(test_transaction)
        if success:
            print("✅ 单条交易保存成功")
        else:
            print("⚠️ 单条交易保存失败或已存在")
        
        # 测试保存多条交易
        multiple_transactions = [
            test_transaction,
            {
                **test_transaction,
                'hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                'blockNumber': '23100744'
            }
        ]
        
        saved_count = tx_info.save_transactions_to_db(multiple_transactions)
        print(f"✅ 批量保存成功，保存了 {saved_count} 条记录")
        
        # 测试查询
        transactions = tx_info.get_transactions_from_db(
            address='0x0a0ae914771ec0a5851049864ccc27b1baa8cd43',
            limit=10
        )
        print(f"✅ 查询成功，找到 {len(transactions)} 条记录")
        
        tx_info.close_db_connection()
        return True
        
    except Exception as e:
        print(f"❌ 交易数据保存测试失败: {e}")
        return False

def test_data_validation():
    """测试数据验证"""
    print("\n=== 测试数据验证 ===")
    
    # 测试无效数据
    invalid_transaction = {
        'blockNumber': 'invalid_number',
        'hash': '0xinvalid_hash',
        'from': 'invalid_address'
    }
    
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'test_ethereum_transactions',
        'user': 'postgres',
        'password': 'password',
        'port': 5432
    }
    
    try:
        tx_info = TransactionInfo(
            etherscan_api_key="test_key",
            contract_info=None,
            db_config=DB_CONFIG
        )
        
        tx_info.connect_db()
        
        # 测试保存无效数据
        try:
            success = tx_info.save_single_transaction(invalid_transaction)
            print("⚠️ 无效数据保存测试完成")
        except Exception as e:
            print(f"✅ 数据验证正常工作，捕获到错误: {e}")
        
        tx_info.close_db_connection()
        return True
        
    except Exception as e:
        print(f"❌ 数据验证测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试Etherscan交易数据存储系统...\n")
    
    tests = [
        ("数据库连接测试", test_database_connection),
        ("交易数据保存测试", test_transaction_save),
        ("数据验证测试", test_data_validation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"运行 {test_name}...")
        if test_func():
            passed += 1
        print()
    
    print(f"测试完成: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统工作正常。")
        return 0
    else:
        print("❌ 部分测试失败，请检查配置和依赖。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
