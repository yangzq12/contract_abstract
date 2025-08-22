#!/usr/bin/env python3
"""
测试MPT相关功能的脚本
"""

import sys
import os
import json
from web3 import Web3

# 添加slither路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'slither'))

def test_mpt_functions():
    """测试MPT相关功能"""
    
    # 模拟Web3连接（实际使用时需要真实的RPC节点）
    w3 = Web3()
    
    # 测试参数
    block_number = 1000000
    contract_address = "0x1234567890123456789012345678901234567890"
    
    try:
        from slither.tools.contract_abstract.onchain.storage_proof import StorageProof
        
        # 创建StorageProof实例
        storage_proof = StorageProof(block_number, contract_address, w3)
        
        print("测试MPT功能:")
        print("=" * 50)
        
        # 测试用例
        test_slots = [0, 1, 2, "0x123", "0x456"]
        
        for slot in test_slots:
            print(f"\n测试slot: {slot}")
            print("-" * 30)
            
            # 1. 测试从trie读取value
            try:
                value = storage_proof.get_value_from_trie(slot)
                print(f"从trie读取value: {value}")
            except Exception as e:
                print(f"从trie读取value失败: {e}")
            
            # 2. 测试生成proof
            try:
                proof_info = storage_proof.generate_proof_for_slot(slot)
                if proof_info:
                    print(f"生成的proof: {json.dumps(proof_info, indent=2)}")
                else:
                    print("生成proof失败")
            except Exception as e:
                print(f"生成proof失败: {e}")
            
            # 3. 测试获取value和proof
            try:
                result = storage_proof.get_storage_with_proof(slot)
                if result:
                    print(f"获取的value和proof: {json.dumps(result, indent=2)}")
                else:
                    print("获取value和proof失败")
            except Exception as e:
                print(f"获取value和proof失败: {e}")
            
            # 4. 测试proof验证
            if proof_info:
                try:
                    verified = storage_proof.verify_proof(
                        slot, 
                        proof_info["value"], 
                        proof_info["proof"], 
                        proof_info["root"]
                    )
                    print(f"Proof验证结果: {verified}")
                except Exception as e:
                    print(f"Proof验证失败: {e}")
        
        # 5. 测试批量获取
        print(f"\n测试批量获取:")
        print("-" * 30)
        try:
            batch_results = storage_proof.batch_get_storage_with_proofs(test_slots)
            print(f"批量获取结果: {json.dumps(batch_results, indent=2)}")
        except Exception as e:
            print(f"批量获取失败: {e}")
        
        # 6. 测试导出proof数据
        print(f"\n测试导出proof数据:")
        print("-" * 30)
        try:
            export_data = storage_proof.export_proof_data(test_slots[0])
            if export_data:
                print(f"导出的proof数据: {json.dumps(export_data, indent=2)}")
            else:
                print("导出proof数据失败")
        except Exception as e:
            print(f"导出proof数据失败: {e}")
            
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保在正确的环境中运行此脚本")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")

def test_trie_operations():
    """测试基本的trie操作"""
    print("\n测试基本trie操作:")
    print("=" * 50)
    
    try:
        from trie import HexaryTrie
        from eth_utils import keccak, to_bytes
        import rlp
        
        # 创建空的trie
        trie = HexaryTrie({})
        
        # 测试插入数据
        test_data = [
            (0, "0x1234567890abcdef"),
            (1, "0xabcdef1234567890"),
            (2, "0x0000000000000000"),
        ]
        
        for slot, value in test_data:
            # 编码key
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            # 编码value
            encoded_value = rlp.encode(to_bytes(int(value, 16)).rjust(32, b"\x00"))
            # 插入trie
            trie.set(key, encoded_value)
            print(f"插入 slot={slot}, value={value}")
        
        # 测试读取数据
        print("\n读取数据:")
        for slot, expected_value in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            encoded_value = trie.get(key)
            if encoded_value:
                decoded_value = rlp.decode(encoded_value)
                actual_value = "0x" + decoded_value.hex()
                print(f"slot={slot}: 期望={expected_value}, 实际={actual_value}")
            else:
                print(f"slot={slot}: 未找到数据")
        
        # 测试生成proof
        print("\n生成proof:")
        for slot, _ in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            proof = trie.get_proof(key)
            print(f"slot={slot}: proof长度={len(proof)}")
        
        # 测试验证proof
        print("\n验证proof:")
        for slot, _ in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            value = trie.get(key)
            proof = trie.get_proof(key)
            verified = trie.verify_proof(trie.root_hash, key, value, proof)
            print(f"slot={slot}: proof验证={verified}")
            
    except ImportError as e:
        print(f"导入trie模块失败: {e}")
        print("请安装必要的依赖: pip install trie eth-utils rlp")
    except Exception as e:
        print(f"trie操作测试失败: {e}")

if __name__ == "__main__":
    test_trie_operations()
    test_mpt_functions()
