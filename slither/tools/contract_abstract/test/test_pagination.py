#!/usr/bin/env python3
"""
测试Etherscan API分页功能
"""

import logging
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from slither.tools.contract_abstract.onchain.transaction_info import TransactionInfo

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pagination():
    """测试分页功能"""
    
    # 测试配置
    test_address = "0xA0b86a33E6441b8c4C8C1C1C1C1C1C1C1C1C1C1C"  # 使用一个测试地址
    etherscan_api_key = "YourApiKeyToken"  # 请替换为您的API密钥
    
    # 创建模拟的合约信息
    class MockContractInfo:
        def __init__(self):
            pass
    
    contract_info = MockContractInfo()
    
    # 创建交易信息实例
    transaction_info = TransactionInfo(
        test_address,
        etherscan_api_key,
        contract_info
    )
    
    # 测试分页功能
    try:
        print("=== 测试分页功能 ===")
        
        # 测试一个较大的区块范围，确保有足够的数据触发分页
        start_block = 18000000  # 示例起始区块
        end_block = 18001000    # 示例结束区块
        
        print(f"测试区块范围: {start_block} - {end_block}")
        print(f"合约地址: {test_address}")
        
        # 获取交易数据
        transactions = transaction_info.get_transactions(start_block, end_block)
        
        print(f"\n✅ 测试完成!")
        print(f"总共获取到 {len(transactions)} 条交易记录")
        
        if len(transactions) > 0:
            print(f"第一条交易哈希: {transactions[0].get('hash', 'N/A')}")
            print(f"最后一条交易哈希: {transactions[-1].get('hash', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_single_page():
    """测试单页数据获取"""
    
    # 测试配置
    test_address = "0xA0b86a33E6441b8c4C8C1C1C1C1C1C1C1C1C1C1C"
    etherscan_api_key = "YourApiKeyToken"
    
    class MockContractInfo:
        def __init__(self):
            pass
    
    contract_info = MockContractInfo()
    transaction_info = TransactionInfo(
        test_address,
        etherscan_api_key,
        contract_info
    )
    
    try:
        print("\n=== 测试单页数据获取 ===")
        
        # 测试一个较小的区块范围
        start_block = 18000000
        end_block = 18000010
        
        print(f"测试区块范围: {start_block} - {end_block}")
        
        # 获取普通交易
        normal_txs = transaction_info._get_transactions(test_address, start_block, end_block, "txlist")
        print(f"普通交易数量: {len(normal_txs)}")
        
        # 获取内部交易
        internal_txs = transaction_info._get_transactions(test_address, start_block, end_block, "txlistinternal")
        print(f"内部交易数量: {len(internal_txs)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 单页测试失败: {e}")
        return False

if __name__ == "__main__":
    print("Etherscan API分页功能测试")
    print("请确保您有有效的Etherscan API密钥")
    print("=" * 50)
    
    # 测试单页功能
    success1 = test_single_page()
    
    # 测试分页功能
    success2 = test_pagination()
    
    if success1 and success2:
        print("\n🎉 所有测试通过!")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
