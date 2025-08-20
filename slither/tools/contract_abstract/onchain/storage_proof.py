import rlp
import pickle
from trie import HexaryTrie
from eth_utils import keccak, to_bytes, decode_hex, encode_hex
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class StorageProof:
    def __init__(self, block_number, contract_address, w3, db_config=None):
        self.block_number = block_number
        self.contract_address = contract_address
        self.w3 = w3
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'storage_trie_db',
            'user': 'postgres',
            'password': 'password'
        }

        self.init_database()
        if not self.load_trie_from_database():
            db = {}
            self.trie = HexaryTrie(db)

    def connect_db(self):
        """连接到PostgreSQL数据库"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试连接MPT数据库: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
                self.db_connection = psycopg2.connect(**self.db_config)
                self.db_connection.autocommit = False
                logger.info("成功连接到MPT数据库")
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
                            logger.info(f"成功连接到MPT数据库 (使用小写名称: {lowercase_db_name})")
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

    def init_database(self):
        """初始化数据库表结构"""
        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # 创建存储trie数据的表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS storage_tries (
                        id SERIAL PRIMARY KEY,
                        contract_address VARCHAR(42) NOT NULL,
                        block_number BIGINT NOT NULL,
                        trie_data BYTEA NOT NULL,
                        trie_root_hash VARCHAR(66) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(contract_address, block_number)
                    )
                """)
                
                # 创建索引以提高查询性能
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contract_block 
                    ON storage_tries(contract_address, block_number)
                """)
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise Exception(f"数据库初始化失败: {e}")
        finally:
            conn.close()

    def save_trie_to_database(self):
        """将当前的storage trie保存到数据库"""
        if not self.db_config:
            raise Exception("数据库配置未设置")
        
        conn = self.connect_db()
        try:
            # 初始化数据库表
            self.init_database()
            
            # 序列化trie数据
            trie_data = pickle.dumps(self.trie.db)
            trie_root = encode_hex(self.trie.root_hash)
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO storage_tries 
                    (contract_address, block_number, trie_data, trie_root_hash)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (contract_address, block_number) 
                    DO UPDATE SET 
                        trie_data = EXCLUDED.trie_data,
                        trie_root_hash = EXCLUDED.trie_root_hash,
                        created_at = CURRENT_TIMESTAMP
                """, (self.contract_address, self.block_number, trie_data, trie_root))
                
                conn.commit()
                print(f"Trie已保存到数据库: 合约={self.contract_address}, 区块={self.block_number}")
                
        except Exception as e:
            conn.rollback()
            raise Exception(f"保存trie到数据库失败: {e}")
        finally:
            conn.close()

    def load_trie_from_database(self):
        """从数据库加载storage trie"""
        if not self.db_config:
            raise Exception("数据库配置未设置")
        
        conn = self.connect_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT trie_data, trie_root_hash 
                    FROM storage_tries 
                    WHERE contract_address = %s AND block_number = %s
                """, (self.contract_address, self.block_number))
                
                result = cursor.fetchone()
                if result:
                    # 反序列化trie数据
                    trie_db = pickle.loads(result['trie_data'])
                    self.trie = HexaryTrie(trie_db)
                    print(f"Trie已从数据库加载: 合约={self.contract_address}, 区块={self.block_number}")
                    return True
                else:
                    print(f"数据库中未找到trie: 合约={self.contract_address}, 区块={self.block_number}")
                    return False
                    
        except Exception as e:
            raise Exception(f"从数据库加载trie失败: {e}")
        finally:
            conn.close()

    def get_trie_info_from_database(self):
        """从数据库获取trie信息（不加载完整trie）"""
        if not self.db_config:
            raise Exception("数据库配置未设置")
        
        conn = self.connect_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT trie_root_hash, created_at 
                    FROM storage_tries 
                    WHERE contract_address = %s AND block_number = %s
                """, (self.contract_address, self.block_number))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'trie_root_hash': result['trie_root_hash'],
                        'created_at': result['created_at']
                    }
                else:
                    return None
                    
        except Exception as e:
            raise Exception(f"获取trie信息失败: {e}")
        finally:
            conn.close()

    def list_available_tries(self):
        """列出数据库中可用的trie"""
        if not self.db_config:
            raise Exception("数据库配置未设置")
        
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT contract_address, block_number, trie_root_hash, created_at 
                    FROM storage_tries 
                    ORDER BY created_at DESC
                """)
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
                    
        except Exception as e:
            raise Exception(f"获取trie列表失败: {e}")
        finally:
            conn.close()

    def delete_trie_from_database(self):
        """从数据库删除当前的trie"""
        if not self.db_config:
            raise Exception("数据库配置未设置")
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM storage_tries 
                    WHERE contract_address = %s AND block_number = %s
                """, (self.contract_address, self.block_number))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"Trie已从数据库删除: 合约={self.contract_address}, 区块={self.block_number}")
                    return True
                else:
                    print(f"数据库中未找到要删除的trie: 合约={self.contract_address}, 区块={self.block_number}")
                    return False
                    
        except Exception as e:
            conn.rollback()
            raise Exception(f"删除trie失败: {e}")
        finally:
            conn.close()

    def get_storage_info(self):
        return self.storage_info
    
    def get_block_number(self):
        return self.block_number

    def get_storage_value(self, slot):
        # slot 可以是 int 或 hex
        if isinstance(slot, int):
            slot = hex(slot)
        return self.w3.eth.get_storage_at(self.contract_address, slot, block_identifier=self.block_number)

    def get_storage_proof(self, slot):
        # slot 必须是 hex string
        if isinstance(slot, int):
            slot = hex(slot)
        result = self.w3.manager.request_blocking(
            "eth_getProof",
            [self.contract_address, [slot], hex(self.block_number)]
        )
        return result

    def update_storage(self, slot, value_hex: str):
        # slot 编码：keccak(pad32(slot))
        key = keccak(to_bytes(slot).rjust(32, b"\x00"))

        # value 编码：RLP(32字节)
        value = int(value_hex, 16)
        if value == 0:
            self.trie.delete(key)
        else:
            encoded_value = rlp.encode(to_bytes(value).rjust(32, b"\x00"))
            self.trie.set(key, encoded_value)

    def sync_slot(self, slot: int):
        value = self.get_storage_value(slot)
        self.update_storage(slot, value)
        return

    def get_local_root(self):
        return encode_hex(self.trie.root_hash)

    def get_block_and_storage_root(self):
        """
        返回区块信息和指定合约地址的 storageRoot
        """
        # 1. 获取区块头
        block = self.w3.eth.get_block(self.block_number, full_transactions=False)

        # 2. 获取账户 proof，从中提取 storageRoot
        # 这里返回 proof 不验证，只取 storageRoot
        proof = self.w3.manager.request_blocking(
            "eth_getProof",
            [self.contract_address, [], hex(self.block_number)]  # 空 slot 列表，只关心 storageRoot
        )
        storage_root = proof["storageHash"]

        return block, storage_root


    
