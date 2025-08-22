#!/usr/bin/env python3
"""
简单的MPT功能测试
"""

def test_basic_trie_operations():
    """测试基本的trie操作"""
    print("测试基本trie操作:")
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
        
        print("插入数据:")
        for slot, value in test_data:
            # 编码key
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            # 编码value
            encoded_value = rlp.encode(to_bytes(int(value, 16)).rjust(32, b"\x00"))
            # 插入trie
            trie.set(key, encoded_value)
            print(f"  插入 slot={slot}, value={value}")
        
        # 测试读取数据
        print("\n读取数据:")
        for slot, expected_value in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            encoded_value = trie.get(key)
            if encoded_value:
                decoded_value = rlp.decode(encoded_value)
                actual_value = "0x" + decoded_value.hex()
                print(f"  slot={slot}: 期望={expected_value}, 实际={actual_value}")
                print(f"    匹配: {expected_value == actual_value}")
            else:
                print(f"  slot={slot}: 未找到数据")
        
        # 测试生成proof
        print("\n生成proof:")
        for slot, _ in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            proof = trie.get_proof(key)
            print(f"  slot={slot}: proof长度={len(proof)}")
            for i, p in enumerate(proof):
                print(f"    proof[{i}]: 0x{p.hex()}")
        
        # 测试验证proof
        print("\n验证proof:")
        for slot, _ in test_data:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            value = trie.get(key)
            proof = trie.get_proof(key)
            verified = trie.verify_proof(trie.root_hash, key, value, proof)
            print(f"  slot={slot}: proof验证={verified}")
        
        # 测试根哈希
        print(f"\nTrie根哈希: 0x{trie.root_hash.hex()}")
        
        return trie
            
    except ImportError as e:
        print(f"导入trie模块失败: {e}")
        print("请安装必要的依赖: pip install trie eth-utils rlp")
        return None
    except Exception as e:
        print(f"trie操作测试失败: {e}")
        return None

def test_proof_verification():
    """测试proof验证功能"""
    print("\n测试proof验证功能:")
    print("=" * 50)
    
    try:
        from trie import HexaryTrie
        from eth_utils import keccak, to_bytes
        import rlp
        
        # 创建trie并插入数据
        trie = HexaryTrie({})
        
        # 插入一些测试数据
        test_slots = [0, 1, 2, 10, 100]
        for slot in test_slots:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            value = rlp.encode(to_bytes(slot * 1000).rjust(32, b"\x00"))
            trie.set(key, value)
        
        print("测试proof验证:")
        
        # 测试存在的key
        for slot in test_slots:
            key = keccak(to_bytes(slot).rjust(32, b"\x00"))
            value = trie.get(key)
            proof = trie.get_proof(key)
            
            # 验证正确的proof
            verified = trie.verify_proof(trie.root_hash, key, value, proof)
            print(f"  slot={slot}: 正确proof验证={verified}")
            
            # 验证错误的value
            wrong_value = rlp.encode(to_bytes(999999).rjust(32, b"\x00"))
            verified_wrong = trie.verify_proof(trie.root_hash, key, wrong_value, proof)
            print(f"  slot={slot}: 错误value验证={verified_wrong}")
        
        # 测试不存在的key
        non_existent_slot = 999
        key = keccak(to_bytes(non_existent_slot).rjust(32, b"\x00"))
        proof = trie.get_proof(key)
        verified_none = trie.verify_proof(trie.root_hash, key, None, proof)
        print(f"  slot={non_existent_slot}: 不存在key验证={verified_none}")
        
    except Exception as e:
        print(f"proof验证测试失败: {e}")

def test_storage_proof_class():
    """测试StorageProof类的功能"""
    print("\n测试StorageProof类功能:")
    print("=" * 50)
    
    try:
        # 模拟Web3对象
        class MockWeb3:
            def __init__(self):
                self.eth = MockEth()
        
        class MockEth:
            def get_storage_at(self, address, slot, block_identifier):
                # 模拟返回一些数据
                return "0x" + "0" * 62 + "01"
            
            def get_block(self, block_number, full_transactions=False):
                return {"number": block_number, "hash": "0x" + "0" * 64}
            
            def manager(self):
                return MockManager()
        
        class MockManager:
            def request_blocking(self, method, params):
                if method == "eth_getProof":
                    return {
                        "storageHash": "0x" + "0" * 64,
                        "storageProof": [{"key": "0x0", "value": "0x0", "proof": []}]
                    }
                return {}
        
        # 导入StorageProof类
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'slither'))
        
        from slither.tools.contract_abstract.onchain.storage_proof import StorageProof
        
        # 创建StorageProof实例
        w3 = MockWeb3()
        storage_proof = StorageProof(1000000, "0x1234567890123456789012345678901234567890", w3)
        
        # 测试基本功能
        print("测试基本功能:")
        
        # 测试get_storage_value
        value = storage_proof.get_storage_value(0)
        print(f"  get_storage_value(0): {value}")
        
        # 测试get_storage_proof
        proof = storage_proof.get_storage_proof(0)
        print(f"  get_storage_proof(0): {proof}")
        
        # 测试get_block_and_storage_root
        block, storage_root = storage_proof.get_block_and_storage_root()
        print(f"  get_block_and_storage_root: block={block}, storage_root={storage_root}")
        
        # 测试trie相关功能
        print("\n测试trie相关功能:")
        
        # 插入一些测试数据到trie
        test_slots = [0, 1, 2]
        for slot in test_slots:
            storage_proof.update_storage(slot, "0x" + "0" * 62 + hex(slot)[2:].zfill(2))
            print(f"  更新storage slot={slot}")
        
        # 测试从trie读取value
        for slot in test_slots:
            value = storage_proof.get_value_from_trie(slot)
            print(f"  get_value_from_trie({slot}): {value}")
        
        # 测试生成proof
        for slot in test_slots:
            proof_info = storage_proof.generate_proof_for_slot(slot)
            if proof_info:
                print(f"  generate_proof_for_slot({slot}): 成功")
                print(f"    proof长度: {len(proof_info['proof'])}")
            else:
                print(f"  generate_proof_for_slot({slot}): 失败")
        
        # 测试获取value和proof
        for slot in test_slots:
            result = storage_proof.get_storage_with_proof(slot)
            if result:
                print(f"  get_storage_with_proof({slot}): 成功")
                print(f"    verified: {result['verified']}")
            else:
                print(f"  get_storage_with_proof({slot}): 失败")
        
    except ImportError as e:
        print(f"导入StorageProof类失败: {e}")
    except Exception as e:
        print(f"StorageProof类测试失败: {e}")

if __name__ == "__main__":
    test_basic_trie_operations()
    test_proof_verification()
    test_storage_proof_class()
