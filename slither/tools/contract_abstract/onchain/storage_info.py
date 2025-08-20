import logging
from slither.tools.contract_abstract.database_manager import DatabaseManager
import requests
import psycopg2
import time
import re
import math
from slither.tools.contract_abstract.onchain.storage_proof import StorageProof

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
        
        # 初始化数据库管理器并设置数据库环境
        self.db_manager = DatabaseManager(self.db_config)
        if not self.db_manager.setup_database():
            raise Exception("数据库环境设置失败")
        
        self.connect_db()
        self.create_init_tables()
        self.revert_threshold = 12
        self.abi = self.transaction_info.abi

        self.storage_proof = StorageProof(0, self.address, self.w3)

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
        self.create_table("simple_entities", simple_attributes, ["id"]) # 该id后续固定为1

    def create_table_for_mapping(self, table_name, entity):
        primary_keys = []
        attributes = []
        self._add_simple_attribute(entity["dataMeta"]["key"], "key1", attributes, "")
        primary_keys.append("key1")
        self._get_mapping_attributes(entity, attributes, primary_keys)
        self.create_table(table_name, attributes, primary_keys)

    def create_table_for_array(self, table_name, entity, read=False):
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

    def sync_storage_to_block(self, block_number):
        changed_slots = []
        block = self.storage_proof.get_block_number()
        while block <= block_number:
            transactions = self.transaction_info.get_transactions_from_etherscan(block, block)
            for tx in transactions:
                pass #TODO: 处理交易


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

    def _get_array_attributes(self, entity, attributes, primary_keys, read=False):
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

    def _get_struct_attributes(self, meta, attributes, prefix="", read=False):
        for field in meta["dataMeta"]["fields"]:
            if field["type"]["dataType"] == "mapping":
                attributes.append(((prefix + field["name"], "TEXT")))
            elif field["type"]["dataType"] == "struct":
                self._get_struct_attributes(field["type"], attributes, prefix + field["name"] + "__", read)
            elif field["type"]["dataType"] == "staticArray" or field["type"]["dataType"] == "dynamicArray":
                attributes.append(((prefix + field["name"], "TEXT")))
            else:
                self._add_simple_attribute(field["type"], field["name"], attributes, prefix, read)

    def _add_simple_attribute(self, element, name, attributes, prefix, read=False):
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




                       
                



