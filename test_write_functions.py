#!/usr/bin/env python3
"""
测试write_elements_to_table功能的脚本
"""

import sys
import os
import json

# 添加slither路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'slither'))

def test_write_functions():
    """测试写入功能"""
    
    try:
        from slither.tools.contract_abstract.onchain.storage_info import StorageInfo
        
        # 模拟必要的参数
        meta_json = {
            "entities": []
        }
        
        class MockContractInfo:
            def __init__(self):
                self.w3 = None
        
        class MockTransactionInfo:
            def __init__(self):
                self.abi = []
        
        # 数据库配置
        db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_storage_db',
            'user': 'postgres',
            'password': 'password'
        }
        
        # 创建StorageInfo实例
        contract_info = MockContractInfo()
        transaction_info = MockTransactionInfo()
        target_address = "0x1234567890123456789012345678901234567890"
        
        storage_info = StorageInfo(meta_json, target_address, contract_info, db_config, transaction_info)
        
        print("测试写入功能:")
        print("=" * 50)
        
        # 测试表名
        test_table = "test_users"
        
        # 1. 测试获取主键信息
        print("\n1. 测试获取主键信息:")
        try:
            primary_keys = storage_info._get_table_primary_keys(test_table)
            print(f"表 {test_table} 的主键: {primary_keys}")
        except Exception as e:
            print(f"获取主键信息失败: {e}")
        
        # 2. 测试插入新记录
        print("\n2. 测试插入新记录:")
        try:
            # 假设表有id主键和name, age字段
            attributes = {
                "id": 1,
                "name": "张三",
                "age": 25,
                "email": "zhangsan@example.com"
            }
            
            result = storage_info.write_elements_to_table(test_table, attributes)
            print(f"插入结果: {result}")
        except Exception as e:
            print(f"插入记录失败: {e}")
        
        # 3. 测试更新现有记录
        print("\n3. 测试更新现有记录:")
        try:
            # 更新同一条记录
            attributes = {
                "id": 1,
                "name": "张三（已更新）",
                "age": 26,
                "email": "zhangsan_updated@example.com"
            }
            
            result = storage_info.write_elements_to_table(test_table, attributes)
            print(f"更新结果: {result}")
        except Exception as e:
            print(f"更新记录失败: {e}")
        
        # 4. 测试插入另一条记录
        print("\n4. 测试插入另一条记录:")
        try:
            attributes = {
                "id": 2,
                "name": "李四",
                "age": 30,
                "email": "lisi@example.com"
            }
            
            result = storage_info.write_elements_to_table(test_table, attributes)
            print(f"插入结果: {result}")
        except Exception as e:
            print(f"插入记录失败: {e}")
        
        # 5. 测试批量写入
        print("\n5. 测试批量写入:")
        try:
            attributes_list = [
                {
                    "id": 3,
                    "name": "王五",
                    "age": 28,
                    "email": "wangwu@example.com"
                },
                {
                    "id": 4,
                    "name": "赵六",
                    "age": 35,
                    "email": "zhaoliu@example.com"
                },
                {
                    "id": 1,  # 更新现有记录
                    "name": "张三（批量更新）",
                    "age": 27,
                    "email": "zhangsan_batch@example.com"
                }
            ]
            
            result = storage_info.batch_write_elements_to_table(test_table, attributes_list)
            print(f"批量写入结果: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"批量写入失败: {e}")
        
        # 6. 测试查询验证
        print("\n6. 测试查询验证:")
        try:
            # 查询所有记录
            results = storage_info.get_elements_from_table(test_table, [], {})
            print(f"查询到 {len(results)} 条记录:")
            for i, record in enumerate(results, 1):
                print(f"  记录 {i}: {json.dumps(record, indent=2)}")
        except Exception as e:
            print(f"查询验证失败: {e}")
        
        # 7. 测试删除记录
        print("\n7. 测试删除记录:")
        try:
            # 删除id为2的记录
            deleted_count = storage_info.delete_elements_from_table(test_table, {"id": 2})
            print(f"删除了 {deleted_count} 条记录")
        except Exception as e:
            print(f"删除记录失败: {e}")
            
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保在正确的环境中运行此脚本")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")

def test_sql_generation():
    """测试SQL生成逻辑"""
    print("\n测试SQL生成逻辑:")
    print("=" * 50)
    
    # 模拟SQL生成逻辑
    def generate_insert_sql(table_name, attributes):
        columns = list(attributes.keys())
        values = list(attributes.values())
        placeholders = ", ".join(["%s"] * len(columns))
        
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        return insert_sql, values
    
    def generate_update_sql(table_name, attributes, primary_keys):
        # 分离主键和非主键字段
        pk_attributes = {pk: attributes[pk] for pk in primary_keys}
        non_pk_attributes = {k: v for k, v in attributes.items() if k not in primary_keys}
        
        if not non_pk_attributes:
            return None, None
        
        # 构建UPDATE语句
        set_clause = ", ".join([f"{col} = %s" for col in non_pk_attributes.keys()])
        where_clause = " AND ".join([f"{pk} = %s" for pk in primary_keys])
        
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        
        # 构建参数列表：先是非主键字段的值，然后是主键字段的值
        params = list(non_pk_attributes.values()) + list(pk_attributes.values())
        
        return update_sql, params
    
    # 测试用例
    test_cases = [
        {
            "name": "单主键插入",
            "table": "users",
            "attributes": {"id": 1, "name": "张三", "age": 25},
            "primary_keys": ["id"]
        },
        {
            "name": "单主键更新",
            "table": "users",
            "attributes": {"id": 1, "name": "张三（更新）", "age": 26},
            "primary_keys": ["id"]
        },
        {
            "name": "复合主键插入",
            "table": "user_roles",
            "attributes": {"user_id": 1, "role_id": 2, "assigned_date": "2024-01-01"},
            "primary_keys": ["user_id", "role_id"]
        },
        {
            "name": "复合主键更新",
            "table": "user_roles",
            "attributes": {"user_id": 1, "role_id": 2, "assigned_date": "2024-01-02"},
            "primary_keys": ["user_id", "role_id"]
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}:")
        
        # 测试INSERT SQL
        insert_sql, insert_params = generate_insert_sql(
            test_case["table"], 
            test_case["attributes"]
        )
        print(f"   INSERT SQL: {insert_sql}")
        print(f"   INSERT 参数: {insert_params}")
        
        # 测试UPDATE SQL
        update_sql, update_params = generate_update_sql(
            test_case["table"], 
            test_case["attributes"],
            test_case["primary_keys"]
        )
        if update_sql:
            print(f"   UPDATE SQL: {update_sql}")
            print(f"   UPDATE 参数: {update_params}")
        else:
            print(f"   UPDATE SQL: 无更新字段")

def test_error_handling():
    """测试错误处理"""
    print("\n测试错误处理:")
    print("=" * 50)
    
    # 模拟错误处理逻辑
    def test_missing_primary_key(attributes, primary_keys):
        missing_keys = [pk for pk in primary_keys if pk not in attributes]
        if missing_keys:
            return f"缺少主键值: {missing_keys}"
        return "主键完整"
    
    # 测试用例
    error_tests = [
        {
            "name": "缺少主键",
            "attributes": {"name": "张三", "age": 25},
            "primary_keys": ["id"]
        },
        {
            "name": "主键完整",
            "attributes": {"id": 1, "name": "张三", "age": 25},
            "primary_keys": ["id"]
        },
        {
            "name": "缺少复合主键",
            "attributes": {"user_id": 1, "assigned_date": "2024-01-01"},
            "primary_keys": ["user_id", "role_id"]
        },
        {
            "name": "复合主键完整",
            "attributes": {"user_id": 1, "role_id": 2, "assigned_date": "2024-01-01"},
            "primary_keys": ["user_id", "role_id"]
        }
    ]
    
    for i, test in enumerate(error_tests, 1):
        print(f"\n{i}. {test['name']}:")
        result = test_missing_primary_key(test["attributes"], test["primary_keys"])
        print(f"   结果: {result}")

if __name__ == "__main__":
    test_sql_generation()
    test_error_handling()
    test_write_functions()
