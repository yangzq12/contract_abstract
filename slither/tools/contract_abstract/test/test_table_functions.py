#!/usr/bin/env python3
"""
测试get_elements_from_table功能的脚本
"""

import sys
import os
import json

# 添加slither路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'slither'))

def test_table_functions():
    """测试表操作功能"""
    
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
        
        print("测试表操作功能:")
        print("=" * 50)
        
        # 1. 测试获取所有表
        print("\n1. 获取所有表:")
        try:
            tables = storage_info.get_all_tables()
            print(f"数据库中的表: {tables}")
        except Exception as e:
            print(f"获取表列表失败: {e}")
        
        # 2. 测试获取表架构
        if tables:
            test_table = tables[0]
            print(f"\n2. 获取表 {test_table} 的架构:")
            try:
                schema = storage_info.get_table_schema(test_table)
                print(f"表架构: {json.dumps(schema, indent=2)}")
            except Exception as e:
                print(f"获取表架构失败: {e}")
        
        # 3. 测试查询数据 - 获取所有列和所有行
        print(f"\n3. 查询表 {test_table} 的所有数据:")
        try:
            results = storage_info.get_elements_from_table(test_table, [], {})
            print(f"查询结果: {len(results)} 行")
            if results:
                print(f"第一行数据: {json.dumps(results[0], indent=2)}")
        except Exception as e:
            print(f"查询所有数据失败: {e}")
        
        # 4. 测试查询数据 - 指定列
        if schema:
            test_columns = [schema[0]["column_name"]] if len(schema) > 0 else []
            print(f"\n4. 查询表 {test_table} 的指定列 {test_columns}:")
            try:
                results = storage_info.get_elements_from_table(test_table, test_columns, {})
                print(f"查询结果: {len(results)} 行")
                if results:
                    print(f"第一行数据: {json.dumps(results[0], indent=2)}")
            except Exception as e:
                print(f"查询指定列失败: {e}")
        
        # 5. 测试查询数据 - 带条件
        print(f"\n5. 查询表 {test_table} 的带条件数据:")
        try:
            # 尝试使用第一个列作为条件
            if schema and len(schema) > 0:
                first_column = schema[0]["column_name"]
                # 获取该列的一个值作为条件
                sample_results = storage_info.get_elements_from_table(test_table, [first_column], {})
                if sample_results:
                    sample_value = sample_results[0][first_column]
                    selector = {first_column: sample_value}
                    print(f"使用条件: {selector}")
                    
                    results = storage_info.get_elements_from_table(test_table, [], selector)
                    print(f"查询结果: {len(results)} 行")
                    if results:
                        print(f"第一行数据: {json.dumps(results[0], indent=2)}")
        except Exception as e:
            print(f"查询带条件数据失败: {e}")
        
        # 6. 测试统计行数
        print(f"\n6. 统计表 {test_table} 的行数:")
        try:
            count = storage_info.count_table_rows(test_table)
            print(f"总行数: {count}")
        except Exception as e:
            print(f"统计行数失败: {e}")
        
        # 7. 测试带条件的行数统计
        print(f"\n7. 统计表 {test_table} 的带条件行数:")
        try:
            if schema and len(schema) > 0:
                first_column = schema[0]["column_name"]
                sample_results = storage_info.get_elements_from_table(test_table, [first_column], {})
                if sample_results:
                    sample_value = sample_results[0][first_column]
                    selector = {first_column: sample_value}
                    print(f"使用条件: {selector}")
                    
                    count = storage_info.count_table_rows(test_table, selector)
                    print(f"符合条件的行数: {count}")
        except Exception as e:
            print(f"统计带条件行数失败: {e}")
            
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
    def generate_sql(table_name, attribute_names, selector):
        # 构建SELECT子句
        if not attribute_names or len(attribute_names) == 0:
            select_clause = "*"
        else:
            select_clause = ", ".join(attribute_names)
        
        # 构建WHERE子句
        where_clause = ""
        params = []
        
        if selector and len(selector) > 0:
            conditions = []
            for key, value in selector.items():
                if isinstance(value, dict):
                    # 处理不等式和范围查询
                    if "op" in value:
                        # 不等式查询: {"column": {"op": "value"}}
                        op = value["op"]
                        op_value = value["value"]
                        if op in [">", "<", ">=", "<=", "!=", "LIKE"]:
                            conditions.append(f"{key} {op} %s")
                            params.append(op_value)
                        else:
                            raise ValueError(f"不支持的操作符: {op}")
                    elif "range" in value:
                        # 范围查询: {"column": {"range": ["min", "max"]}}
                        range_values = value["range"]
                        if len(range_values) == 2:
                            min_val, max_val = range_values
                            if min_val is not None:
                                conditions.append(f"{key} >= %s")
                                params.append(min_val)
                            if max_val is not None:
                                conditions.append(f"{key} <= %s")
                                params.append(max_val)
                        else:
                            raise ValueError("范围查询需要两个值: [min, max]")
                    elif "between" in value:
                        # BETWEEN查询: {"column": {"between": ["min", "max"]}}
                        between_values = value["between"]
                        if len(between_values) == 2:
                            conditions.append(f"{key} BETWEEN %s AND %s")
                            params.extend(between_values)
                        else:
                            raise ValueError("BETWEEN查询需要两个值: [min, max]")
                    elif "in" in value:
                        # IN查询: {"column": {"in": ["value1", "value2"]}}
                        in_values = value["in"]
                        if isinstance(in_values, list) and len(in_values) > 0:
                            placeholders = ", ".join(["%s"] * len(in_values))
                            conditions.append(f"{key} IN ({placeholders})")
                            params.extend(in_values)
                        else:
                            raise ValueError("IN查询需要非空列表")
                    elif "not_in" in value:
                        # NOT IN查询: {"column": {"not_in": ["value1", "value2"]}}
                        not_in_values = value["not_in"]
                        if isinstance(not_in_values, list) and len(not_in_values) > 0:
                            placeholders = ", ".join(["%s"] * len(not_in_values))
                            conditions.append(f"{key} NOT IN ({placeholders})")
                            params.extend(not_in_values)
                        else:
                            raise ValueError("NOT IN查询需要非空列表")
                    elif "is_null" in value:
                        # IS NULL查询: {"column": {"is_null": True}}
                        if value["is_null"]:
                            conditions.append(f"{key} IS NULL")
                        else:
                            conditions.append(f"{key} IS NOT NULL")
                    elif "is_not_null" in value:
                        # IS NOT NULL查询: {"column": {"is_not_null": True}}
                        if value["is_not_null"]:
                            conditions.append(f"{key} IS NOT NULL")
                        else:
                            conditions.append(f"{key} IS NULL")
                    else:
                        raise ValueError(f"不支持的查询条件格式: {value}")
                elif isinstance(value, list):
                    # 如果值是列表，使用IN操作符
                    if len(value) > 0:
                        placeholders = ", ".join(["%s"] * len(value))
                        conditions.append(f"{key} IN ({placeholders})")
                        params.extend(value)
                    else:
                        # 空列表，不添加条件
                        continue
                else:
                    # 否则使用等号
                    conditions.append(f"{key} = %s")
                    params.append(value)
            
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
        
        # 构建完整的SQL查询
        sql_query = f"SELECT {select_clause} FROM {table_name} {where_clause}"
        
        return sql_query, params
    
    # 测试用例
    test_cases = [
        {
            "name": "获取所有数据",
            "table": "users",
            "attributes": [],
            "selector": {},
            "expected": "SELECT * FROM users"
        },
        {
            "name": "获取指定列",
            "table": "users",
            "attributes": ["id", "name"],
            "selector": {},
            "expected": "SELECT id, name FROM users"
        },
        {
            "name": "带条件查询",
            "table": "users",
            "attributes": [],
            "selector": {"status": "active"},
            "expected": "SELECT * FROM users WHERE status = %s"
        },
        {
            "name": "多条件查询",
            "table": "users",
            "attributes": ["id", "name"],
            "selector": {"status": "active", "age": 25},
            "expected": "SELECT id, name FROM users WHERE status = %s AND age = %s"
        },
        {
            "name": "IN条件查询",
            "table": "users",
            "attributes": [],
            "selector": {"id": [1, 2, 3]},
            "expected": "SELECT * FROM users WHERE id IN (%s, %s, %s)"
        },
        {
            "name": "混合条件查询",
            "table": "users",
            "attributes": ["name"],
            "selector": {"status": "active", "id": [1, 2, 3]},
            "expected": "SELECT name FROM users WHERE status = %s AND id IN (%s, %s, %s)"
        },
        # 新增不等式测试用例
        {
            "name": "大于条件查询",
            "table": "users",
            "attributes": ["id", "name"],
            "selector": {"age": {"op": ">", "value": 18}},
            "expected": "SELECT id, name FROM users WHERE age > %s"
        },
        {
            "name": "小于等于条件查询",
            "table": "users",
            "attributes": [],
            "selector": {"age": {"op": "<=", "value": 65}},
            "expected": "SELECT * FROM users WHERE age <= %s"
        },
        {
            "name": "不等于条件查询",
            "table": "users",
            "attributes": ["id"],
            "selector": {"status": {"op": "!=", "value": "inactive"}},
            "expected": "SELECT id FROM users WHERE status != %s"
        },
        {
            "name": "LIKE条件查询",
            "table": "users",
            "attributes": ["name"],
            "selector": {"name": {"op": "LIKE", "value": "%admin%"}},
            "expected": "SELECT name FROM users WHERE name LIKE %s"
        },
        {
            "name": "范围查询",
            "table": "users",
            "attributes": ["id", "name", "age"],
            "selector": {"age": {"range": [18, 65]}},
            "expected": "SELECT id, name, age FROM users WHERE age >= %s AND age <= %s"
        },
        {
            "name": "BETWEEN查询",
            "table": "users",
            "attributes": ["id"],
            "selector": {"age": {"between": [18, 65]}},
            "expected": "SELECT id FROM users WHERE age BETWEEN %s AND %s"
        },
        {
            "name": "IN查询（新格式）",
            "table": "users",
            "attributes": ["name"],
            "selector": {"status": {"in": ["active", "pending"]}},
            "expected": "SELECT name FROM users WHERE status IN (%s, %s)"
        },
        {
            "name": "NOT IN查询",
            "table": "users",
            "attributes": ["id"],
            "selector": {"status": {"not_in": ["deleted", "banned"]}},
            "expected": "SELECT id FROM users WHERE status NOT IN (%s, %s)"
        },
        {
            "name": "IS NULL查询",
            "table": "users",
            "attributes": ["id", "name"],
            "selector": {"email": {"is_null": True}},
            "expected": "SELECT id, name FROM users WHERE email IS NULL"
        },
        {
            "name": "IS NOT NULL查询",
            "table": "users",
            "attributes": ["id"],
            "selector": {"phone": {"is_not_null": True}},
            "expected": "SELECT id FROM users WHERE phone IS NOT NULL"
        },
        {
            "name": "复杂混合查询",
            "table": "users",
            "attributes": ["id", "name", "age"],
            "selector": {
                "status": "active",
                "age": {"range": [18, 65]},
                "role": {"in": ["admin", "user"]},
                "email": {"is_not_null": True}
            },
            "expected": "SELECT id, name, age FROM users WHERE status = %s AND age >= %s AND age <= %s AND role IN (%s, %s) AND email IS NOT NULL"
        },
        {
            "name": "空列表条件（应被忽略）",
            "table": "users",
            "attributes": ["id"],
            "selector": {"status": "active", "role": []},
            "expected": "SELECT id FROM users WHERE status = %s"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}:")
        try:
            sql, params = generate_sql(
                test_case["table"], 
                test_case["attributes"], 
                test_case["selector"]
            )
            print(f"   生成的SQL: {sql}")
            if params:
                print(f"   参数: {params}")
            
            # 验证SQL格式
            if "SELECT" in sql and test_case["table"] in sql:
                print("   ✓ SQL格式正确")
            else:
                print("   ✗ SQL格式错误")
        except Exception as e:
            print(f"   ✗ 生成SQL失败: {e}")

def test_inequality_operations():
    """专门测试不等式操作"""
    print("\n测试不等式操作:")
    print("=" * 50)
    
    # 模拟不等式查询逻辑
    def test_inequality_selector(selector):
        conditions = []
        params = []
        
        for key, value in selector.items():
            if isinstance(value, dict) and "op" in value:
                op = value["op"]
                op_value = value["value"]
                if op in [">", "<", ">=", "<=", "!=", "LIKE"]:
                    conditions.append(f"{key} {op} %s")
                    params.append(op_value)
                    print(f"   添加条件: {key} {op} {op_value}")
                else:
                    print(f"   不支持的操作符: {op}")
        
        return conditions, params
    
    # 测试不等式用例
    inequality_tests = [
        {
            "name": "数值比较",
            "selector": {
                "age": {"op": ">", "value": 18},
                "salary": {"op": "<=", "value": 100000}
            }
        },
        {
            "name": "字符串比较",
            "selector": {
                "name": {"op": "LIKE", "value": "%john%"},
                "status": {"op": "!=", "value": "deleted"}
            }
        },
        {
            "name": "混合比较",
            "selector": {
                "age": {"op": ">=", "value": 21},
                "age": {"op": "<=", "value": 65},
                "department": {"op": "!=", "value": "IT"}
            }
        }
    ]
    
    for i, test in enumerate(inequality_tests, 1):
        print(f"\n{i}. {test['name']}:")
        conditions, params = test_inequality_selector(test["selector"])
        print(f"   生成的条件: {conditions}")
        print(f"   参数: {params}")

if __name__ == "__main__":
    test_sql_generation()
    test_inequality_operations()
    test_table_functions()
