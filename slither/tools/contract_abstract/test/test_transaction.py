#!/usr/bin/env python3
"""
测试事务处理功能
"""

import logging
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from slither.tools.contract_abstract.database_manager import DatabaseManager
from slither.tools.contract_abstract.onchain.transaction_info import TransactionInfo
from slither.tools.contract_abstract.onchain.contract_info import ContractInfo

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_database_connection():
    """测试数据库连接和事务处理"""
    
    # 数据库配置
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ethereum_transactions_test',
        'user': 'postgres',
        'password': 'password'
    }
    
    # 测试合约配置
    test_address = "0x1234567890123456789012345678901234567890"
    etherscan_api_key = "test_key"
    
    try:
        print("=== 测试数据库管理器 ===")
        
        # 创建数据库管理器
        db_manager = DatabaseManager(db_config)
        
        # 设置数据库环境
        if db_manager.setup_database():
            print("✅ 数据库环境设置成功")
        else:
            print("❌ 数据库环境设置失败")
            return False
        
        print("\n=== 测试交易信息类 ===")
        
        # 创建合约信息（模拟）
        class MockContractInfo:
            def __init__(self):
                pass
        
        contract_info = MockContractInfo()
        
        # 创建交易信息实例
        transaction_info = TransactionInfo(
            test_address,
            etherscan_api_key,
            contract_info,
            db_config=db_config
        )
        
        print("✅ 交易信息类初始化成功")
        
        # 测试获取最新区块号
        latest_block = transaction_info.get_latest_block_number()
        print(f"✅ 获取最新区块号: {latest_block}")
        
        # 测试获取区块范围
        block_range = transaction_info.get_block_range()
        print(f"✅ 获取区块范围: {block_range}")
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)
