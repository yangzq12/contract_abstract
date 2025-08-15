import logging
from slither.tools.contract_abstract.database_manager import DatabaseManager
import requests
import psycopg2
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class StorageInfo:
    def __init__(self, meta_json, target_address, contract_info, db_config, transaction_info,logic_address=None):
        self.contract_info = contract_info
        self.w3 = contract_info.w3
        self.address = target_address
        self.transaction_info = transaction_info
        self.logic_address = logic_address
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
                table_name = entity_name
                primary_keys = []
                attributes = []
                attributes.append(("key1", "TEXT"))
                primary_keys.append("key1")
                self._get_mapping_attributes(entity, attributes, primary_keys)
                self.create_table(table_name, attributes, primary_keys)
            elif entity["dataType"] == "struct":
                prefix = entity_name + "."
                self._get_struct_attributes(entity, simple_attributes, prefix)
            else:
                self._add_simple_attribute(entity["dataType"], entity_name, simple_attributes, "")
        self.create_table("simple_entities", simple_attributes, ["id"]) # 该id后续固定为1

    def create_table(self, table_name, attributes, primary_keys):
        if not self.db_connection:
            self.connect_db()
        
        cursor = self.db_connection.cursor()

        attributes_str = []
        for attribute in attributes:
            if len(primary_keys) == 1 and primary_keys[0] == attribute[0]:
                attribute_str = f"{attribute_str} PRIMARY KEY"
            else:
                attribute_str = f"{attribute[0]} {attribute[1]}"
            attributes_str.append(attribute_str)
        
        primary_keys_str = ""
        if len(primary_keys) > 1:
            primary_keys_str = f"PRIMARY KEY ({', '.join(primary_keys)})"


        if primary_keys_str != "":
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(attributes)}
            );
             """
        else:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(attributes)},
                {primary_keys_str}
            );
             """

        cursor.execute(create_table_sql)
        self.db_connection.commit()
        cursor.close()

    def _get_mapping_attributes(self, entity, attributes, primary_keys):
        if entity["dataMeta"]["value"]["dataType"] == "mapping":
            depth = len(primary_keys)
            attributes.append((f"key{depth+1}", "TEXT"))
            primary_keys.append("key{depth+1}")
            self._get_mapping_attributes(entity["dataMeta"]["value"], attributes, primary_keys)
        elif entity["dataMeta"]["value"]["dataType"] == "struct":
            self._get_struct_attributes(entity["dataMeta"]["value"], attributes)
        else:
            self._add_simple_attribute(entity["dataMeta"]["value"]["dataType"], "value", attributes, "")

    def _get_struct_attributes(self, meta, attributes, prefix=""):
        for field in meta["dataMeta"]["fields"]:
            if field["type"]["dataType"] == "mapping":
                attributes.append(((prefix + field["name"], "TEXT")))
            elif field["type"]["dataType"] == "struct":
                self.get_struct_attributes(field["type"], attributes, prefix + field["name"] + ".")
            elif field["type"]["dataType"] == "staticArray" or field["type"]["dataType"] == "dynamicArray":
                attributes.append(((prefix + field["name"], "TEXT")))
            else:
                self._add_simple_attribute(field["type"]["dataType"], field["name"], attributes, prefix)

    def _add_simple_attribute(self, element_type, name, attributes, prefix):
        if "int" in element_type:
            attributes.append(((prefix + name, "NUMERIC(65,0)")))
        elif "bool" in element_type:
            attributes.append(((prefix + name, "BOOLEAN")))
        elif "address" in element_type:
            attributes.append(((prefix + name, "VARCHAR(42)")))
        else:
            attributes.append(((prefix + name, "TEXT")))




                       
                



