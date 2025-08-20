#!/usr/bin/env python3
"""
StorageProof PostgreSQL功能测试脚本
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from storage_proof import StorageProof


def test_database_operations():
    """测试数据库操作功能"""
    
    # 模拟数据库配置（实际使用时需要真实的PostgreSQL连接）
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'storage_trie_db',
        'user': 'postgres',
        'password': 'test_password'
    }
    
    # 模拟Web3对象（实际使用时需要真实的Web3连接）
    class MockWeb3:
        def __init__(self):
            self.eth = MockEth()
            self.manager = MockManager()
    
    class MockEth:
        def get_storage_at(self, address, slot, block_identifier):
            return "0x0000000000000000000000000000000000000000000000000000000000000001"
        
        def get_block(self, block_number, full_transactions=False):
            return {
                'number': block_number,
                'hash': '0x' + '0' * 64,
                'timestamp': 1234567890
            }
    
    class MockManager:
        def request_blocking(self, method, params):
            if method == "eth_getProof":
                return {
                    "storageHash": "0x" + "0" * 64,
                    "storageProof": []
                }
    
    # 创建模拟对象
    mock_w3 = MockWeb3()
    
    # 测试参数
    contract_address = "0x1234567890123456789012345678901234567890"
    block_number = 1000000
    
    print("=== StorageProof PostgreSQL功能测试 ===\n")
    
    try:
        # 1. 测试创建实例
        print("1. 测试创建StorageProof实例...")
        storage_proof = StorageProof(block_number, contract_address, mock_w3, db_config)
        print("   ✓ 实例创建成功")
        
        # 2. 测试数据库连接（会失败，因为没有真实的数据库）
        print("\n2. 测试数据库连接...")
        try:
            storage_proof.get_db_connection()
            print("   ✓ 数据库连接成功")
        except Exception as e:
            print(f"   ⚠ 数据库连接失败（预期）: {e}")
        
        # 3. 测试trie操作
        print("\n3. 测试trie操作...")
        try:
            # 模拟同步槽位
            storage_proof.sync_slot(0)
            storage_proof.sync_slot(1)
            print("   ✓ Trie槽位同步成功")
            
            # 获取根哈希
            root_hash = storage_proof.get_local_root()
            print(f"   ✓ Trie根哈希: {root_hash}")
            
        except Exception as e:
            print(f"   ✗ Trie操作失败: {e}")
        
        # 4. 测试其他方法
        print("\n4. 测试其他方法...")
        try:
            block_num = storage_proof.get_block_number()
            print(f"   ✓ 区块号: {block_num}")
            
            # 测试获取存储值
            value = storage_proof.get_storage_value(0)
            print(f"   ✓ 存储值: {value}")
            
        except Exception as e:
            print(f"   ✗ 其他方法测试失败: {e}")
        
        print("\n=== 测试完成 ===")
        print("\n注意：")
        print("- 数据库连接测试失败是预期的，因为没有真实的PostgreSQL数据库")
        print("- 要完整测试数据库功能，请设置真实的PostgreSQL数据库")
        print("- 运行 'python storage_proof_example.py --setup' 查看设置指南")
        
    except Exception as e:
        print(f"测试失败: {e}")


def test_imports():
    """测试导入功能"""
    print("=== 测试导入功能 ===\n")
    
    try:
        import requests
        print("✓ requests 导入成功")
    except ImportError:
        print("✗ requests 导入失败")
    
    try:
        import rlp
        print("✓ rlp 导入成功")
    except ImportError:
        print("✗ rlp 导入失败")
    
    try:
        from trie import HexaryTrie
        print("✓ trie 导入成功")
    except ImportError:
        print("✗ trie 导入失败")
    
    try:
        from eth_utils import keccak, to_bytes, decode_hex, encode_hex
        print("✓ eth_utils 导入成功")
    except ImportError:
        print("✗ eth_utils 导入失败")
    
    try:
        import psycopg2
        print("✓ psycopg2 导入成功")
    except ImportError:
        print("✗ psycopg2 导入失败")
    
    try:
        from psycopg2.extras import RealDictCursor
        print("✓ psycopg2.extras 导入成功")
    except ImportError:
        print("✗ psycopg2.extras 导入失败")


if __name__ == "__main__":
    print("StorageProof PostgreSQL功能测试\n")
    
    # 测试导入
    test_imports()
    print()
    
    # 测试数据库操作
    test_database_operations()
