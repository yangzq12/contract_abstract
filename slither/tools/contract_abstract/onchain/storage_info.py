import logging
from slither.tools.contract_abstract.database_manager import DatabaseManager
import requests
import psycopg2
import time
import re
import math
import copy
from slither.tools.contract_abstract.onchain.storage_proof import StorageProof
from eth_utils import keccak
from slither.tools.contract_abstract.contract.entity import Entity

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class StorageInfo:
    def __init__(self, meta_json, target_address, contract_info, db_config, transaction_info):
        self.contract_info = contract_info
        self.w3 = contract_info.w3
        self.address = target_address
        self.transaction_info = transaction_info
        self.db_config = db_config 
        self.db_connection = None
        self.meta_json = meta_json
        self.entity = Entity(target_address, None, contract_info, meta_json["entities"])
        self.deal_with_function_write_storage()
        
        # 初始化数据库管理器并设置数据库环境
        self.db_manager = DatabaseManager(self.db_config)
        if not self.db_manager.setup_database():
            raise Exception("数据库环境设置失败")
        
        self.connect_db()
        self.create_init_tables()
        self.revert_threshold = 12
        self.abi = self.transaction_info.abi

        self.simple_table_name = "simple_entities"

        self.storage_proof = StorageProof(0, self.address, self.w3)
        self.function_write_storage = {}

    def connect_db(self):
        """连接到PostgreSQL数据库"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试连接Storage数据库: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
                self.db_connection = psycopg2.connect(**self.db_config)
                self.db_connection.autocommit = False
                logger.info("成功连接到Storage数据库")
                return
            except psycopg2.OperationalError as e:
                error_msg = str(e).lower()
                logger.error(f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                if "database" in error_msg and "does not exist" in error_msg:
                    # 尝试使用小写数据库名称连接
                    original_db_name = self.db_config['database']
                    lowercase_db_name = original_db_name.lower()
                    
                    if original_db_name != lowercase_db_name:
                        logger.info(f"尝试使用小写数据库名称连接: {lowercase_db_name}")
                        try:
                            temp_config = self.db_config.copy()
                            temp_config['database'] = lowercase_db_name
                            self.db_connection = psycopg2.connect(**temp_config)
                            self.db_connection.autocommit = False
                            logger.info(f"成功连接到Storage数据库 (使用小写名称: {lowercase_db_name})")
                            # 更新配置中的数据库名称为小写
                            self.db_config['database'] = lowercase_db_name
                            return
                        except psycopg2.OperationalError as e2:
                            logger.error(f"使用小写数据库名称连接也失败: {e2}")
                    
                    logger.error(f"数据库 {self.db_config['database']} 不存在")
                    logger.info("请确保数据库已创建，或者检查数据库管理器是否正确运行")
                    raise
                elif "authentication failed" in error_msg:
                    logger.error("数据库认证失败，请检查用户名和密码")
                    raise
                elif "connection refused" in error_msg:
                    logger.error("无法连接到PostgreSQL服务，请确保服务正在运行")
                    raise
                elif attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error("数据库连接失败，已达到最大重试次数")
                    raise
            except Exception as e:
                logger.error(f"数据库连接时发生未知错误: {e}")
                raise
    
    def create_init_tables(self):
        """创建合约storage数据表"""
        entities = self.meta_json["entities"]

        simple_attributes = []
        simple_attributes.append(("id", "INTEGER"))
        for entity_name in entities:
            entity = entities[entity_name]
            if entity["dataType"] == "mapping":
                self.create_table_for_mapping(entity_name, entity)
            elif entity["dataType"] == "struct":
                prefix = entity_name + "__"
                self._get_struct_attributes(entity, simple_attributes, prefix)
            elif entity["dataType"] == "staticArray" or entity["dataType"] == "dynamicArray":
                self.create_table_for_array(entity_name, entity)
            else:
                self._add_simple_attribute(entity, entity_name, simple_attributes, "")
        simple_attributes.append(("block_number", "BIGINT")) # 用于记录当前storage状态是那个block的
        simple_attributes.append(("block_hash", "VARCHAR(66)")) # 用于记录当前storage状态是那个block的hash
        self.create_table(self.simple_table_name, simple_attributes, ["id"]) # 该id后续固定为1

    def create_table_for_mapping(self, table_name, entity):
        primary_keys = []
        attributes = []
        self._add_simple_attribute(entity["dataMeta"]["key"], "key1", attributes, "")
        primary_keys.append("key1")
        self._get_mapping_attributes(entity, attributes, primary_keys)
        self.create_table(table_name, attributes, primary_keys)

    def create_table_for_array(self, table_name, entity, read=True):
        primary_keys = []
        attributes = []
        attributes.append(("key1", "BIGINT"))
        primary_keys.append("key1")
        self._get_array_attributes(entity, attributes, primary_keys, read)
        self.create_table(table_name, attributes, primary_keys)

    def sync_storage(self):
        latest_block = self.transaction_info.get_latest_block_number()
        current_block = self.storage_proof.get_block_number()
        contract_creation_block = self.transaction_info.get_contract_creation_block()
        if contract_creation_block > current_block:
            self.storage_proof.block_number = contract_creation_block - 1
        self.sync_storage_to_block(latest_block)

    def deal_with_function_write_storage(self):
        for function in self.meta_json["function_write_storage"]:
            parameters = self.meta_json["function_write_storage"][function]["parameters"]
            write_storages = self.meta_json["function_write_storage"][function]["write_storages"]
            hash_bytes = keccak(text=function)
            hash_bytes = hash_bytes[0:4]
            hash_str = "0x" + hash_bytes.hex()
            self.function_write_storage[hash_str] = {"parameters": parameters, "write_storages": []}
            for write_storage in write_storages:
                parsed_expr = Entity.parse_expr(write_storage)
                self.function_write_storage[hash_str]["write_storages"].append(parsed_expr)

    def sync_storage_to_block(self, block_number):
        changed_slots = set()
        block = self.storage_proof.get_block_number()
        while block <= block_number:
            transactions = self.transaction_info.get_transactions_from_etherscan(block, block)
            for tx in transactions:
                if tx["input_data"] != "" and tx["input_data"] is not None and tx["input_data"] != "0x":
                    func_name, params = self.decode_input(tx["input_data"])
                    method_id = tx["method_id"]
                    if method_id in self.function_write_storage:
                        for write_storage_expr in self.function_write_storage[method_id]["write_storages"]:
                            self.get_changed_slots(params, write_storage_expr, changed_slots)  
                    else:
                        logger.error(f"无法解析交易: {tx['hash']}, with input: {tx['input_data']}")
        
       
    def init_syn_storage(self):
        for entity in self.meta_json["entities"]:
            if entity["dataType"] == "mapping":
                pass
            elif entity["dataType"] == "struct":
                
            elif entity["dataType"] == "staticArray" or entity["dataType"] == "dynamicArray":
                pass
            else: # 简单类型
                slot_info = entity["storageInfo"]
                type = entity["dataType"]
                value = self.entity.get_storage_value(slot_info, type)
                #将value存入到simple_table中
                self.write_elements_to_table(self.simple_table_name, {entity["name"]: value, "id": 1})


                

    def get_changed_slots(self, params, write_expr, changed_slots):
        if isinstance(write_expr["name"], str):
            if write_expr["name"] in self.entity.storage_meta:
                results = self.deal_with_index(write_expr, params)
                for result in results:
                    slot_info, type_info = self.entity.get_storage_slot_info(result["name"])
                    changed_slots.add({"slot": slot_info["slot"], "expr": result["name"]})
            else:
                raise Exception(f"storage {write_expr['name']} not found in meta")
        else:
            raise Exception(f"write_expr['name'] is not a string")

    def deal_with_index(self, write_exprs, params):
        result_exprs = []
        for write_expr in write_exprs:
            if write_expr["index"] is not None:
                if write_expr["index"]["index"] is None: # 一层的index，如a[b]
                    results = self.deal_with_index_name(write_expr["index"], params)
                    for result in results:
                        new_expr = {"name": write_expr["name"]+"["+str(result)+"]", "index": None, "field": write_expr["index"]["field"]}
                    result_exprs.extend(self.deal_with_index(new_expr, params))
                else: # 两层的index，如a[b][c]
                    raise Exception("two layer index is not supported")
            elif write_expr["field"] is not None:
                new_expr = {"name": write_expr["name"]+"."+write_expr["field"], "index": write_expr["field"]["index"], "field": write_expr["field"]["field"]}
                result_exprs.extend(self.deal_with_index(new_expr, params))
            else:
                pass
        return result_exprs

    def deal_with_index_name(self, index_expr, params):
        #index["name"]可能是b或者b.c或者b[c]或者b[c].d
        type_info = self.entity.storage_meta[index_expr["name"]]
        assert type_info["dataType"] in ["mapping", "staticArray", "dynamicArray"]
        if isinstance(index_expr["index"]["name"], str): #index为一层，如果可以解析出具体就解析出具体，如果不能就给出所有的index
            if index_expr["index"]["name"] in self.entity.storage_meta:
                results =self.read_elements_from_table(self.simple_table_name, index_expr["index"]["name"], {})
                value = results[0][index_expr["index"]["name"]]
                return [value]
            elif index_expr["index"]["name"] in params:
                return [params[index_expr["index"]["name"]]]
            else:
                results = self.read_elements_from_table(index_expr["name"], ["key1"], {})
                return_results = []
                for x in results:
                    return_results.append(x["key1"])
                return return_results
        elif isinstance(index_expr["index"]["name"], dict): # index内部还有层次机构，比如a[b.c]或则a[b[c]]，其他情况暂时不处理
            index_name = index_expr["index"]["name"]
            if isinstance(index_name["name"], str):
                if index_name["name"] in self.entity.storage_meta:
                    if index_name["index"] is not None: #a[b[c]]的形式或者a[b[c].d]的形式
                        assert isinstance(index_name["index"]["name"], str)
                        assert index_name["index"]["index"] is None
                        if index_name["index"]["field"] is None: #a[b[c]]的形式
                            if index_name["index"]["name"] in self.entity.storage_meta:
                                inner_results =self.read_elements_from_table(self.simple_table_name, index_expr["index"]["name"], {})
                                value = inner_results[0][index_name["index"]["name"]]
                                outter_results = self.read_elements_from_table(index_name["name"], ["value"], {"key1": value})
                                return [outter_results[0]["value"]]
                            elif index_name["index"]["name"] in params:
                                value = params[index_expr["index"]["name"]]
                                outter_results = self.read_elements_from_table(index_name["name"], ["value"], {"key1": value})
                                return [outter_results[0]["value"]]
                            else:
                                outter_results =self.read_elements_from_table(index_name["name"], ["value"], {})
                                return_results = []
                                for x in outter_results:
                                    return_results.append(x["value"])
                                return return_results
                        else: # a[b[c].d]的形式
                            assert isinstance(index_name["index"]["field"]["name"], str)
                            assert index_name["index"]["field"]["index"] is None
                            assert index_name["index"]["field"]["field"] is None
                            field_name = index_name["index"]["field"]["name"]
                            if index_name["index"]["name"] in self.entity.storage_meta:
                                inner_results =self.read_elements_from_table(self.simple_table_name, index_expr["index"]["name"], {})
                                value = inner_results[0][index_name["index"]["name"]]
                                outter_results = self.read_elements_from_table(index_name["name"], [field_name], {"key1": value})
                                return [outter_results[0][field_name]]
                            elif index_name["index"]["name"] in params:
                                value = params[index_expr["index"]["name"]]
                                outter_results = self.read_elements_from_table(index_name["name"], [field_name], {"key1": value})
                                return [outter_results[0][field_name]]
                            else:
                                outter_results =self.read_elements_from_table(index_name["name"], [field_name], {})
                                return_results = []
                                for x in outter_results:
                                    return_results.append(x[field_name])
                                return return_results        
                    elif index_name["field"] is not None: #a[b.c]的形式
                        assert isinstance(index_name["field"]["name"])
                        assert index_name["field"]["index"] is None
                        assert index_name["field"]["field"] is None
                        results = self.read_elements_from_table(self.simple_table_name, index_name["name"]+"__"+index_name["field"]["name"], {})
                        value = results[0][index_name["name"]+"__"+index_name["field"]["name"]]
                        return [value]
                    else:
                        raise Exception(f"index_name['index'] is not None, but {index_name['index']}")
                else:
                    raise Exception(f"{index_name} not found in meta")
            else:
                raise Exception(f"index_expr['index']['name'] is not a string, but {index_name}")

    def read_elements_from_table(self, table_name, attribute_names, selector):
        """
        从指定表中获取数据
        Args:
            table_name: 表名
            attribute_names: 要获取的属性名列表，如果为空数组则返回所有属性
            selector: 选择条件字典，支持以下格式：
                - 简单等值: {"column": "value"}
                - IN查询: {"column": ["value1", "value2"]}
                - 不等式: {"column": {"op": "value"}} 其中op可以是 >, <, >=, <=, !=, LIKE
                - 范围查询: {"column": {"range": ["min", "max"]}}
        Returns:
            list: 查询结果列表，每个元素是一个字典
        """
        if not self.db_connection:
            self.connect_db()
        
        cursor = self.db_connection.cursor()
        
        try:
            # 构建SELECT子句
            if not attribute_names or len(attribute_names) == 0:
                # 如果属性名为空数组，则选择所有列
                select_clause = "*"
            else:
                # 否则选择指定的属性
                select_clause = ", ".join(attribute_names)
            
            # 构建WHERE子句
            where_clause = ""
            params = []
            
            if selector and len(selector) > 0:
                # 如果有选择条件，构建WHERE子句
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
            
            logger.info(f"执行SQL查询: {sql_query}")
            if params:
                logger.info(f"查询参数: {params}")
            
            # 执行查询
            cursor.execute(sql_query, params)
            
            # 获取列名
            if attribute_names and len(attribute_names) > 0:
                column_names = attribute_names
            else:
                column_names = [desc[0] for desc in cursor.description]
            
            # 获取结果
            rows = cursor.fetchall()
            
            # 将结果转换为字典列表
            results = []
            for row in rows:
                row_dict = {}
                for i, column_name in enumerate(column_names):
                    row_dict[column_name] = row[i]
                results.append(row_dict)
            
            logger.info(f"查询完成，返回 {len(results)} 行数据")
            return results
            
        except Exception as e:
            logger.error(f"查询表 {table_name} 失败: {e}")
            raise Exception(f"查询表 {table_name} 失败: {e}")
        finally:
            cursor.close()

    def write_elements_to_table(self, table_name, attributes):
        """
        将元素添加或修改到数据库表格中
        Args:
            table_name: 表名
            attributes: 属性名和属性值的对应字典，包括主键的值
        Returns:
            bool: 操作是否成功
        """
        if not self.db_connection:
            self.connect_db()
        
        cursor = self.db_connection.cursor()
        
        try:
            # 获取表的主键信息
            primary_keys = self._get_table_primary_keys(table_name)
            if not primary_keys:
                raise Exception(f"无法获取表 {table_name} 的主键信息")
            
            # 检查是否提供了所有主键的值
            missing_keys = [pk for pk in primary_keys if pk not in attributes]
            if missing_keys:
                raise Exception(f"缺少主键值: {missing_keys}")
            
            # 构建主键条件用于检查记录是否存在
            pk_conditions = []
            pk_params = []
            for pk in primary_keys:
                pk_conditions.append(f"{pk} = %s")
                pk_params.append(attributes[pk])
            
            # 检查记录是否存在
            check_sql = f"SELECT COUNT(*) FROM {table_name} WHERE {' AND '.join(pk_conditions)}"
            cursor.execute(check_sql, pk_params)
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # 记录存在，执行UPDATE操作
                return self._update_record(cursor, table_name, attributes, primary_keys)
            else:
                # 记录不存在，执行INSERT操作
                return self._insert_record(cursor, table_name, attributes)
                
        except Exception as e:
            logger.error(f"写入表 {table_name} 失败: {e}")
            self.db_connection.rollback()
            raise Exception(f"写入表 {table_name} 失败: {e}")
        finally:
            cursor.close()

    def _get_table_primary_keys(self, table_name):
        """
        获取表的主键信息
        Args:
            table_name: 表名
        Returns:
            list: 主键列名列表
        """
        cursor = self.db_connection.cursor()
        
        try:
            # 查询主键信息
            sql_query = """
                SELECT c.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name)
                JOIN information_schema.columns AS c ON c.table_schema = tc.constraint_schema
                  AND tc.table_name = c.table_name AND ccu.column_name = c.column_name
                WHERE constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
                ORDER BY c.ordinal_position
            """
            
            cursor.execute(sql_query, (table_name,))
            primary_keys = [row[0] for row in cursor.fetchall()]
            
            return primary_keys
            
        except Exception as e:
            logger.error(f"获取表 {table_name} 主键信息失败: {e}")
            return []
        finally:
            cursor.close()

    def _insert_record(self, cursor, table_name, attributes):
        """
        插入新记录
        Args:
            cursor: 数据库游标
            table_name: 表名
            attributes: 属性字典
        Returns:
            bool: 操作是否成功
        """
        # 构建INSERT语句
        columns = list(attributes.keys())
        values = list(attributes.values())
        placeholders = ", ".join(["%s"] * len(columns))
        
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        logger.info(f"执行INSERT: {insert_sql}")
        logger.info(f"参数: {values}")
        
        cursor.execute(insert_sql, values)
        self.db_connection.commit()
        
        logger.info(f"成功插入记录到表 {table_name}")
        return True

    def _update_record(self, cursor, table_name, attributes, primary_keys):
        """
        更新现有记录
        Args:
            cursor: 数据库游标
            table_name: 表名
            attributes: 属性字典
            primary_keys: 主键列表
        Returns:
            bool: 操作是否成功
        """
        # 分离主键和非主键字段
        pk_attributes = {pk: attributes[pk] for pk in primary_keys}
        non_pk_attributes = {k: v for k, v in attributes.items() if k not in primary_keys}
        
        if not non_pk_attributes:
            logger.info(f"没有非主键字段需要更新，跳过UPDATE操作")
            return True
        
        # 构建UPDATE语句
        set_clause = ", ".join([f"{col} = %s" for col in non_pk_attributes.keys()])
        where_clause = " AND ".join([f"{pk} = %s" for pk in primary_keys])
        
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        
        # 构建参数列表：先是非主键字段的值，然后是主键字段的值
        params = list(non_pk_attributes.values()) + list(pk_attributes.values())
        
        logger.info(f"执行UPDATE: {update_sql}")
        logger.info(f"参数: {params}")
        
        cursor.execute(update_sql, params)
        self.db_connection.commit()
        
        logger.info(f"成功更新记录到表 {table_name}")
        return True

    def create_table(self, table_name, attributes, primary_keys):
        if not self.db_connection:
            self.connect_db()
        
        cursor = self.db_connection.cursor()

        attributes_str = []
        has_meaning = False
        for attribute in attributes:
            if len(primary_keys) == 1 and primary_keys[0] == attribute[0]:
                attribute_str = f"{attribute[0]} {attribute[1]} PRIMARY KEY"
            else:
                attribute_str = f"{attribute[0]} {attribute[1]}"
            attributes_str.append(attribute_str)
            if attribute[0] not in primary_keys: # 处理primary keys之外还有其他需要记录的属性，则表示该table有意义
                has_meaning = True
        
        if not has_meaning:
            return
        
        primary_keys_str = ""
        if len(primary_keys) > 1:
            primary_keys_str = f"PRIMARY KEY ({', '.join(primary_keys)})"


        if primary_keys_str != "":
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(attributes_str)},
                {primary_keys_str}
            );
             """
        else:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(attributes_str)}
            );
             """

        cursor.execute(create_table_sql)
        self.db_connection.commit()
        cursor.close()

    def _get_mapping_attributes(self, entity, attributes, primary_keys):
        if entity["dataMeta"]["value"]["dataType"] == "mapping":
            depth = len(primary_keys)
            self._add_simple_attribute(entity["dataMeta"]["key"], f"key{depth+1}", attributes, "")
            primary_keys.append(f"key{depth+1}")
            self._get_mapping_attributes(entity["dataMeta"]["value"], attributes, primary_keys)
        elif entity["dataMeta"]["value"]["dataType"] == "struct":
            self._get_struct_attributes(entity["dataMeta"]["value"], attributes)
        else:
            self._add_simple_attribute(entity["dataMeta"]["value"], "value", attributes, "")

    def _get_array_attributes(self, entity, attributes, primary_keys, read=True):
        if entity["dataMeta"]["elementType"]["dataType"] == "mapping":
            raise Exception("mapping in array is not supported")
        elif entity["dataMeta"]["elementType"]["dataType"] == "struct":
            self._get_struct_attributes(entity["dataMeta"]["elementType"], attributes, "", read)
        elif entity["dataMeta"]["elementType"]["dataType"] == "staticArray" or entity["dataMeta"]["elementType"]["dataType"] == "dynamicArray":
            depth = len(primary_keys)
            attributes.append((f"key{depth+1}", "BIGINT"))
            primary_keys.append(f"key{depth+1}")
            self._get_array_attributes(entity["dataMeta"]["elementType"], attributes, primary_keys, read)
        else:
            self._add_simple_attribute(entity["dataMeta"]["elementType"], "value", attributes, "", read)    

    def _get_struct_attributes(self, meta, attributes, prefix="", read=True):
        for field in meta["dataMeta"]["fields"]:
            if field["type"]["dataType"] == "mapping":
                attributes.append(((prefix + field["name"], "TEXT")))
            elif field["type"]["dataType"] == "struct":
                self._get_struct_attributes(field["type"], attributes, prefix + field["name"] + "__", read)
            elif field["type"]["dataType"] == "staticArray" or field["type"]["dataType"] == "dynamicArray":
                attributes.append(((prefix + field["name"], "TEXT")))
            else:
                self._add_simple_attribute(field["type"], field["name"], attributes, prefix, read)

    def _add_simple_attribute(self, element, name, attributes, prefix, read=True):
        element_type = element["dataType"]
        if not read:
            if "read" in element:
                read = element["read"]
            else:
                if "key" in name:
                    read = True
        if "bitmap" in element:
            bitmap = element["bitmap"]
        else:
            bitmap = None
        if read and bitmap is None: # 只有有读标记的storage才会被存储
            if "int" in element_type:
                size = self.extract_number(element_type)
                if "u" in element_type:
                    signed = False
                else:
                    signed = True
                if size is None:
                    m = self.bits_to_numeric(256, signed)
                    attributes.append(((prefix + name, f"NUMERIC({m},0)")))
                else:
                    if size <= 16:
                        attributes.append(((prefix + name, "SMALLINT")))
                    elif size <= 32:
                        attributes.append(((prefix + name, "INTEGER")))
                    elif size <= 64:
                        attributes.append(((prefix + name, "BIGINT")))
                    else:
                        m = self.bits_to_numeric(size, signed)
                        attributes.append(((prefix + name, f"NUMERIC({m},0)")))
            elif "bool" in element_type:
                attributes.append(((prefix + name, "BOOLEAN")))
            elif "address" in element_type:
                attributes.append(((prefix + name, "VARCHAR(42)")))
            else:
                attributes.append(((prefix + name, "TEXT")))
        elif read and bitmap is not None:
            if "int" in element_type:
                size = self.extract_number(element_type)
                if size == 256:
                    attributes.append(((prefix + name, f"BYTEA CHECK (length({prefix + name}) = 32)")))
                    if bitmap["dataType"] == "struct":
                        prefix = prefix + name + "__"
                        self._get_struct_attributes(bitmap, attributes, prefix, read=True)
                    elif bitmap["dataType"] == "staticArray":
                        # self.create_table_for_array(prefix + name, bitmap, read=True)
                        pass
                    else:
                        raise Exception("bitmap is only supported for struct and staticArray type")
                else:
                    raise Exception("bitmap is only supported for 256 bits int type")
            else:
                raise Exception("bitmap is only supported for int type")

    def decode_input(self, tx_input):
        contract = self.w3.eth.contract(abi=self.abi)
        try:
            func_obj, params = contract.decode_function_input(tx_input)
            return func_obj.fn_name, params
        except Exception:
            return None, None

    def extract_number(self, s):
        match = re.search(r'(\d+)$', s)
        return int(match.group(1)) if match else None

    def bits_to_numeric(self, size: int, signed: bool):
        """
        将整数的位数（bits）转换为 PostgreSQL 的 NUMERIC(m,0) 类型。
        
        参数:
            size (int): 位数，比如 8, 16, 32, 64, 128, 256。
            signed (bool): 是否是有符号整数，默认 True。
            
        返回:
            str: NUMERIC(m,0)
        """
        if signed:
            m = math.ceil((size - 1) * math.log10(2))  # 有符号
        else:
            m = math.ceil(size * math.log10(2))        # 无符号
        return m

    


                       
                



