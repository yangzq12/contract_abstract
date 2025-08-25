import logging
from slither.tools.contract_abstract.database_manager import DatabaseManager
import requests
import psycopg2
import time
import re
import math
import copy
from eth_abi import decode, encode
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
        self.revert_threshold = 12
        self.abi = self.transaction_info.abi

        self.simple_table_name = "simple_entities"

        self.storage_proof = StorageProof(0, self.address, self.w3)
        self.function_write_storage = {}

        self.deal_with_function_write_storage()
        
        # 初始化数据库管理器并设置数据库环境
        self.db_manager = DatabaseManager(self.db_config)
        if not self.db_manager.setup_database():
            raise Exception("数据库环境设置失败")
        
        self.connect_db()
        self.create_init_tables()
       
        self.fact_keys = None
        if not self.import_fact_keys_from_json("output/fact_keys.json"):
            self.get_all_keys_for_mapping()
            self.export_fact_keys_to_json("output/fact_keys.json")

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

    def sync_storage_to_block(self, block_number): # 一个交易一个交易的同步storage
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
        
       
    def init_syn_storage(self): # 最开始批量同步合约的storage，因为如果从第一个交易开始同步，存在大量请求的问题
        for entity_name in self.meta_json["entities"]:
            entity = self.meta_json["entities"][entity_name]
            if entity["dataType"] == "mapping":
                if entity_name in self.fact_keys:
                    if entity["dataMeta"]["value"]["dataType"] == "mapping": # 两层mapping
                        assert entity["dataMeta"]["value"]["dataType"]["value"]["dataType"] != "mapping"
                        for key in self.fact_keys[entity_name]:
                            keys = {"key1": key[0], "key2": key[1]}
                            self._init_mapping_entity(entity, entity_name, "", entity["storageInfo"], keys)
                    else:
                        base_slot = entity["storageInfo"]["slot"]
                        key_type = entity["dataMeta"]["key"]["dataType"]
                        for key in self.fact_keys[entity_name]:
                            slot_bytes = keccak(encode([key_type, "uint256"], [key, base_slot]))
                            slot_int = int.from_bytes(slot_bytes, "big")
                            slot_info = {"slot": slot_int, "offset": 0}
                            keys = {"key1": key}
                            self._init_mapping_entity(entity, entity_name, "", slot_info, keys)
            elif entity["dataType"] == "struct":
                prefix = entity_name + "__"
                self._init_struct_entity(entity, self.simple_table_name, prefix, entity["storageInfo"], {"id": 1})
            elif entity["dataType"] == "staticArray" or entity["dataType"] == "dynamicArray":
                self._init_array_entity(entity, entity_name, entity["storageInfo"])
            else: # 简单类型
                slot_info = entity["storageInfo"]
                type = entity["dataType"]
                value = self.entity.get_storage_value(slot_info, type)
                #将value存入到simple_table中
                self.write_elements_to_table(self.simple_table_name, {entity_name: value, "id": 1})      

    def _init_array_entity(self, entity, table_name, slot_info):
        base_slot = slot_info["slot"] 
        assert slot_info["offset"] == 0
        slot = keccak(base_slot)
        slot_int = int.from_bytes(slot, "big")
        type = {
            "dataType": "uint256",
            "dataMeta": {
                "size": 32
            }
        }
        length = self.entity.get_storage_value(slot_info, type)
        element_type = entity["dataMeta"]["elementType"]
        if element_type["dataType"] == "struct":
            for i in range(length):
                slot_info = {"slot": slot_int + i, "offset": 0}
                self._init_struct_entity(element_type, table_name, "", slot_info, {"key1": i})
        elif element_type["dataType"] == "staticArray":
            raise Exception("Unimplemented type: staticArray")
        elif element_type["dataType"] == "dynamicArray":
            raise Exception("Unimplemented type: dynamicArray")
        elif element_type["dataType"] == "mapping":
            raise Exception("Unimplemented type: "+element_type["dataType"])
        else:
            for i in range(length):
                slot_info = {"slot": slot_int + i, "offset": 0}
                value = self.entity.get_storage_value(slot_info, element_type)
                self.write_elements_to_table(table_name, {"key1": i, "value": value})

    def _init_struct_entity(self, entity, table_name, prefix, base_slot, keys):
        for field in entity["dataMeta"]["fields"]:
            if field["type"]["dataType"] == "mapping":
                add_slot, offset, index = Entity.get_slot_info_for_structure(entity, field["name"])
                assert index != -1
                value = base_slot["slot"] + add_slot
                selector = {prefix + field["name"]: value}
                for key in keys:
                    selector[key] = keys[key]
                self.write_elements_to_table(table_name, selector)
                self.create_table_for_mapping("table_"+str(value), field["type"])
                #TODO: 向表格中加入内容
            elif field["type"]["dataType"] == "struct":
                add_slot, offset, index = Entity.get_slot_info_for_structure(entity, field["name"])
                assert index != -1
                slot_info = {"slot": base_slot["slot"] + add_slot, "offset": offset}
                self._init_struct_entity(field["type"], table_name, prefix + field["name"] + "__", slot_info, keys)
            elif field["type"]["dataType"] == "staticArray" or field["type"]["dataType"] == "dynamicArray":
                add_slot, offset, index = Entity.get_slot_info_for_structure(entity, field["name"])
                assert index != -1
                value = base_slot["slot"] + add_slot
                selector = {prefix + field["name"]: value}
                for key in keys:
                    selector[key] = keys[key]
                self.write_elements_to_table(table_name, selector)
                self.create_table_for_array("table_"+str(value), field["type"])
                #向表格中加入内容
                self._init_array_entity(field["type"], "table_"+str(value), {"slot": value, "offset": 0})
            else:
                add_slot, offset, index = Entity.get_slot_info_for_structure(entity, field["name"])
                assert index != -1
                slot_info = {"slot": base_slot["slot"] + add_slot, "offset": offset}
                type = field["type"]
                value = self.entity.get_storage_value(slot_info, type)
                selector = {prefix + field["name"]: value}
                for key in keys:
                    selector[key] = keys[key]
                self.write_elements_to_table(table_name, selector)

    def _init_mapping_entity(self, entity, table_name, prefix, slot_info, keys):
        if entity["dataMeta"]["value"]["dataType"] == "mapping":
            raise Exception("Unimplemented mapping type in mapping type")
        elif entity["dataMeta"]["value"]["dataType"] == "struct":
            self._init_struct_entity(entity["dataMeta"]["value"], table_name, prefix, slot_info, keys)
        elif entity["dataMeta"]["value"]["dataType"] == "staticArray" or entity["dataMeta"]["value"]["dataType"] == "dynamicArray":
            raise Exception("Unimplemented array type in mapping type")
        else:
            slot_info = entity["storageInfo"]
            type = entity["dataType"]
            value = self.entity.get_storage_value(slot_info, type)
            selector = {prefix + "value": value}
            for key in keys:
                selector[key] = keys[key]
            #将value存入到mapping的table中
            self.write_elements_to_table(table_name, selector) 
            

    def get_all_keys_for_mapping(self):
        # 先分析function_write_storage，得到每个funciton对可能的mapping的entity可能引用的keys
        all_keys = {}
        for function in self.function_write_storage:
            parameters = self.function_write_storage[function]["parameters"]
            write_storages = self.function_write_storage[function]["write_storages"]
            for write_storage in write_storages:
                entity_name = write_storage["name"]
                if entity_name in self.entity.storage_meta:
                    if self.entity.storage_meta[entity_name]["dataType"] == "mapping":
                        if self.entity.storage_meta[entity_name]["dataMeta"]["value"]["dataType"] == "mapping": #双层mapping
                            assert self.entity.storage_meta[entity_name]["dataMeta"]["value"]["dataMeta"]["value"]["dataType"] != "mapping" #不处理三层及以上mapping
                            first_index = write_storage["index"]
                            second_index = write_storage["index"]["index"]
                            if isinstance(first_index["name"], str) and isinstance(second_index["name"], str):
                                if (first_index["name"] in parameters or first_index["name"] == "$msg_sender") and (second_index["name"] in parameters or second_index["name"] == "$msg_sender"):
                                    if function not in all_keys:
                                        all_keys[function] = {}
                                    if entity_name not in all_keys[function]:
                                        all_keys[function][entity_name] = set()
                                    all_keys[function][entity_name].add((first_index["name"], second_index["name"]))
                        else:# 一层mapping
                            index = write_storage["index"]
                            if index is None: # 没有index说明对所有key都写, 暂时不处理，因为没有一般由于gas限制没有这样的情况
                                logger.warning(f"function {function} write {entity_name} with no index, which is not supported")
                            elif isinstance(index["name"], str):
                                if index["name"] in parameters or index["name"] == "$msg_sender":
                                    if function not in all_keys:
                                        all_keys[function] = {}
                                    if entity_name not in all_keys[function]:
                                        all_keys[function][entity_name] = set()
                                    all_keys[function][entity_name].add(index["name"])
                            else:
                                if isinstance(index["name"]["name"], str): # 两层index并且是因为input是数组的关系
                                    if index["name"]["name"] in parameters or index["name"]["name"] == "$msg_sender":
                                        if function not in all_keys:
                                            all_keys[function] = {}
                                        if entity_name not in all_keys[function]:
                                            all_keys[function][entity_name] = set()
                                        all_keys[function][entity_name].add(index["name"]["name"])
        # 然后实际根据交易参数的实际值得到每个mapping的entity实际的key
        latest_block = self.transaction_info.get_latest_block_number()
        contract_creation_block = self.transaction_info.get_contract_creation_block()
        transactions_gen = self.transaction_info.get_transactions_paginated(contract_creation_block, latest_block, page_size=10000)
        fact_keys = {}
        for transactions in transactions_gen:
            for tx in transactions:
                if tx["is_error"] == 0 and tx["input_data"] != "" and tx["input_data"] is not None and tx["input_data"] != "0x":
                    func_name, params = self.decode_input(tx["input_data"])
                    method_id = tx["method_id"]
                    if method_id in all_keys:
                        for entity_name in all_keys[method_id]:
                            for index in all_keys[method_id][entity_name]:
                                if isinstance(index, tuple):
                                    key_1 = []
                                    key_2 = []
                                    if index[0] == "$msg_sender":
                                        key_1.append(tx["from_address"])
                                    else:
                                        if index[0] in params:
                                            if isinstance(params[index[0]], list):
                                                for param in params[index[0]]:
                                                    key_1.append(param)
                                            else:
                                                key_1.append(params[index[0]])
                                        else:
                                            raise Exception(f"{index[0]} not found in params for function {method_id}")
                                    if index[1] == "$msg_sender":
                                        key_2.append(tx["from_address"])
                                    else:
                                        if index[1] in params:
                                            if isinstance(params[index[1]], list):
                                                for param in params[index[1]]:
                                                    key_2.append(param)
                                            else:
                                                key_2.append(params[index[1]])
                                        else:
                                            raise Exception(f"{index[1]} not found in params for function {method_id}")
                                    for index_1 in key_1:
                                        for index_2 in key_2:
                                            if entity_name not in fact_keys:
                                                fact_keys[entity_name] = set()
                                            fact_keys[entity_name].add((index_1,index_2))
                                else:
                                    if index == "$msg_sender":
                                        if entity_name not in fact_keys:
                                            fact_keys[entity_name] = set()
                                        fact_keys[entity_name].add(tx["from_address"])
                                    else:
                                        if index in params:
                                            if entity_name not in fact_keys:
                                                fact_keys[entity_name] = set()
                                            if isinstance(params[index], list):
                                                for param in params[index]:
                                                    fact_keys[entity_name].add(param)
                                            else:
                                                fact_keys[entity_name].add(params[index])
                                        else:
                                            raise Exception(f"{index} not found in params for function {method_id}")
        self.fact_keys = fact_keys
        return fact_keys

    def export_fact_keys_to_json(self, output_file: str, include_metadata: bool = True) -> bool:
        """
        将fact_keys导出到JSON文件
        
        Args:
            output_file: 输出文件路径
            include_metadata: 是否包含元数据信息（合约地址、时间戳等）
            
        Returns:
            bool: 导出是否成功
        """
        try:
            # 准备导出数据
            export_data = {}
            
            # 添加元数据
            if include_metadata:
                export_data['metadata'] = {
                    'contract_address': self.address,
                    'export_timestamp': time.time(),
                    'export_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'total_entities': len(self.fact_keys) if self.fact_keys else 0
                }
            
            # 转换fact_keys为可序列化的格式
            serializable_fact_keys = {}
            if self.fact_keys:
                for entity_name, keys_set in self.fact_keys.items():
                    # 将set转换为list以便JSON序列化
                    serializable_fact_keys[entity_name] = list(keys_set)
            
            export_data['fact_keys'] = serializable_fact_keys
            
            # 写入JSON文件
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"fact_keys已成功导出到: {output_file}")
            logger.info(f"导出实体数量: {len(serializable_fact_keys)}")
            
            # 统计总key数量
            total_keys = sum(len(keys) for keys in serializable_fact_keys.values())
            logger.info(f"导出key总数: {total_keys}")
            
            return True
            
        except Exception as e:
            logger.error(f"导出fact_keys到JSON文件失败: {e}")
            return False

    def import_fact_keys_from_json(self, input_file: str, merge_mode: str = 'replace') -> bool:
        """
        从JSON文件导入fact_keys
        
        Args:
            input_file: 输入文件路径
            merge_mode: 合并模式 ('replace', 'merge', 'append')
                - replace: 完全替换现有的fact_keys
                - merge: 合并到现有的fact_keys中
                - append: 追加到现有的fact_keys中（可能重复）
                
        Returns:
            bool: 导入是否成功
        """
        try:
            import json
            
            # 读取JSON文件
            with open(input_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # 验证文件格式
            if 'fact_keys' not in import_data:
                logger.error("JSON文件格式错误：缺少'fact_keys'字段")
                return False
            
            # 获取导入的fact_keys
            imported_fact_keys = import_data['fact_keys']
            
            # 转换回set格式
            converted_fact_keys = {}
            for entity_name, keys_list in imported_fact_keys.items():
                converted_fact_keys[entity_name] = set(keys_list)
            
            # 根据合并模式处理数据
            if merge_mode == 'replace':
                self.fact_keys = converted_fact_keys
                logger.info("完全替换现有的fact_keys")
                
            elif merge_mode == 'merge':
                if not self.fact_keys:
                    self.fact_keys = {}
                
                for entity_name, keys_set in converted_fact_keys.items():
                    if entity_name not in self.fact_keys:
                        self.fact_keys[entity_name] = set()
                    self.fact_keys[entity_name].update(keys_set)
                logger.info("合并到现有的fact_keys中")
                
            elif merge_mode == 'append':
                if not self.fact_keys:
                    self.fact_keys = {}
                
                for entity_name, keys_set in converted_fact_keys.items():
                    if entity_name not in self.fact_keys:
                        self.fact_keys[entity_name] = set()
                    self.fact_keys[entity_name].update(keys_set)
                logger.info("追加到现有的fact_keys中")
                
            else:
                logger.error(f"不支持的合并模式: {merge_mode}")
                return False
            
            # 显示导入统计信息
            if 'metadata' in import_data:
                metadata = import_data['metadata']
                logger.info(f"从文件导入fact_keys: {input_file}")
                logger.info(f"原始合约地址: {metadata.get('contract_address', 'Unknown')}")
                logger.info(f"导出时间: {metadata.get('export_time', 'Unknown')}")
            
            total_entities = len(converted_fact_keys)
            total_keys = sum(len(keys) for keys in converted_fact_keys.values())
            logger.info(f"导入实体数量: {total_entities}")
            logger.info(f"导入key总数: {total_keys}")
            
            return True
            
        except FileNotFoundError:
            logger.error(f"文件不存在: {input_file}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON文件格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"从JSON文件导入fact_keys失败: {e}")
            return False
                                

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
        # if "bitmap" in element:
        #     bitmap = element["bitmap"]
        # else:
        bitmap = None # TODO: 先不处理bitmap
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

    def close_connection(self):
        """
        手动关闭数据库连接
        """
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None
            logger.info("数据库连接已关闭")

    def __del__(self):
        """
        析构函数，确保在对象销毁时关闭数据库连接
        """
        self.close_connection()


                       
                



