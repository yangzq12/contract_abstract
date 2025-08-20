import subprocess
import time
import logging
import os
import platform
import psycopg2
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DatabaseManager:
    """PostgreSQL数据库管理器"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.system = platform.system().lower()
        self.postgres_running = False
        
    def check_postgres_installed(self) -> bool:
        """检查PostgreSQL是否已安装"""
        try:
            if self.system == "darwin":  # macOS
                result = subprocess.run(["which", "postgres"], 
                                      capture_output=True, text=True, check=False)
                return result.returncode == 0
            elif self.system == "linux":
                result = subprocess.run(["which", "postgres"], 
                                      capture_output=True, text=True, check=False)
                return result.returncode == 0
            elif self.system == "windows":
                # Windows下检查PostgreSQL安装路径
                possible_paths = [
                    r"C:\Program Files\PostgreSQL",
                    r"C:\Program Files (x86)\PostgreSQL"
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        return True
                return False
            else:
                logger.warning(f"不支持的操作系统: {self.system}")
                return False
        except Exception as e:
            logger.error(f"检查PostgreSQL安装时发生错误: {e}")
            return False
    
    def get_postgres_service_name(self) -> str:
        """获取PostgreSQL服务名称"""
        if self.system == "darwin":  # macOS
            return "postgresql"
        elif self.system == "linux":
            # 尝试不同的服务名称
            service_names = ["postgresql", "postgresql-14", "postgresql-13", "postgresql-12"]
            for name in service_names:
                try:
                    result = subprocess.run(["systemctl", "status", name], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0:
                        return name
                except:
                    continue
            return "postgresql"  # 默认名称
        elif self.system == "windows":
            return "postgresql"
        else:
            return "postgresql"
    
    def check_postgres_running(self) -> bool:
        """检查PostgreSQL服务是否正在运行"""
        try:
            # 先尝试连接到默认的postgres数据库来检查服务状态
            temp_config = self.db_config.copy()
            temp_config['database'] = 'postgres'
            
            conn = psycopg2.connect(**temp_config)
            conn.close()
            return True
        except psycopg2.OperationalError as e:
            # 如果是连接被拒绝，说明服务没有运行
            if "Connection refused" in str(e):
                logger.debug("PostgreSQL服务未运行")
                return False
            else:
                logger.debug(f"PostgreSQL连接错误: {e}")
                return False
        except Exception as e:
            logger.debug(f"检查PostgreSQL服务状态时发生错误: {e}")
            return False
    
    def start_postgres_service(self) -> bool:
        """启动PostgreSQL服务"""
        try:
            if self.system == "darwin":  # macOS
                # 使用brew启动PostgreSQL
                logger.info("尝试使用brew启动PostgreSQL...")
                result = subprocess.run(["brew", "services", "start", "postgresql"], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务启动成功")
                    return True
                else:
                    logger.warning(f"brew启动失败: {result.stderr}")
                    
                # 尝试直接启动PostgreSQL进程
                logger.info("尝试直接启动PostgreSQL进程...")
                result = subprocess.run(["pg_ctl", "-D", "/usr/local/var/postgres", "start"], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL进程启动成功")
                    return True
                else:
                    logger.warning(f"pg_ctl启动失败: {result.stderr}")
                    
            elif self.system == "linux":
                service_name = self.get_postgres_service_name()
                logger.info(f"尝试启动PostgreSQL服务: {service_name}")
                result = subprocess.run(["sudo", "systemctl", "start", service_name], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务启动成功")
                    return True
                else:
                    logger.warning(f"systemctl启动失败: {result.stderr}")
                    
            elif self.system == "windows":
                logger.info("尝试启动PostgreSQL服务...")
                result = subprocess.run(["net", "start", "postgresql"], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务启动成功")
                    return True
                else:
                    logger.warning(f"net start失败: {result.stderr}")
            
            return False
            
        except Exception as e:
            logger.error(f"启动PostgreSQL服务时发生错误: {e}")
            return False
    
    def create_database_if_not_exists(self) -> bool:
        """如果数据库不存在则创建"""
        try:
            # 临时连接到默认数据库
            temp_config = self.db_config.copy()
            temp_config['database'] = 'postgres'  # 连接到默认数据库
            
            logger.info(f"尝试连接到默认数据库: {temp_config['host']}:{temp_config['port']}")
            conn = psycopg2.connect(**temp_config)
            conn.autocommit = True  # 创建数据库时需要autocommit=True
            cursor = conn.cursor()
            
            # 检查目标数据库是否存在
            # logger.info(f"检查数据库是否存在: {self.db_config['database']}")
            # logger.info(f"数据库名称类型: {type(self.db_config['database'])}")
            # logger.info(f"数据库名称长度: {len(self.db_config['database'])}")
            # logger.info(f"数据库名称字节表示: {self.db_config['database'].encode('utf-8')}")
            
            # 列出所有数据库进行调试
            # cursor.execute("SELECT datname FROM pg_database")
            # all_databases = cursor.fetchall()
            # logger.info(f"所有数据库: {[db[0] for db in all_databases]}")
            
            # 检查是否有匹配的数据库（不区分大小写）
            # matching_dbs = [db[0] for db in all_databases if db[0].lower() == self.db_config['database'].lower()]
            # logger.info(f"匹配的数据库: {matching_dbs}")
            
            # 使用不区分大小写的查询
            cursor.execute("SELECT 1 FROM pg_database WHERE LOWER(datname) = LOWER(%s)", 
                         (self.db_config['database'],))
            
            result = cursor.fetchone()
            # logger.info(f"查询结果: {result}")
            # logger.info(f"查询结果类型: {type(result)}")
            
            if not result:
                logger.info(f"数据库 {self.db_config['database']} 不存在，正在创建...")
                try:
                    cursor.execute(f"CREATE DATABASE {self.db_config['database']}")
                    logger.info(f"数据库 {self.db_config['database']} 创建成功")
                except psycopg2.Error as e:
                    if "permission denied" in str(e).lower():
                        logger.error(f"权限不足，无法创建数据库: {e}")
                        logger.info("请使用具有创建数据库权限的用户，或者手动创建数据库:")
                        logger.info(f"  sudo -u postgres psql -c \"CREATE DATABASE {self.db_config['database']};\"")
                        logger.info(f"  sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {self.db_config['database']} TO {self.db_config['user']};\"")
                        return False
                    else:
                        logger.error(f"创建数据库失败: {e}")
                        return False
            else:
                logger.info(f"数据库 {self.db_config['database']} 已存在")
            
            # 检查用户是否有访问目标数据库的权限
            try:
                cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{self.db_config['database']}' AND datacl IS NOT NULL")
                if cursor.fetchone():
                    logger.info("检查数据库访问权限...")
                    # 尝试连接到目标数据库
                    test_config = self.db_config.copy()
                    test_conn = psycopg2.connect(**test_config)
                    test_conn.close()
                    logger.info("数据库访问权限正常")
                else:
                    logger.warning("数据库权限信息不可用，将尝试直接连接")
            except psycopg2.Error as e:
                logger.error(f"数据库访问权限检查失败: {e}")
                logger.info("请确保用户具有访问数据库的权限:")
                logger.info(f"  sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {self.db_config['database']} TO {self.db_config['user']};\"")
                return False
            
            cursor.close()
            conn.close()
            return True
            
        except psycopg2.OperationalError as e:
            if "authentication failed" in str(e).lower():
                logger.error(f"数据库认证失败: {e}")
                logger.info("请检查用户名和密码是否正确")
                return False
            elif "connection refused" in str(e).lower():
                logger.error(f"无法连接到PostgreSQL服务: {e}")
                logger.info("请确保PostgreSQL服务正在运行")
                return False
            else:
                logger.error(f"数据库连接错误: {e}")
                return False
        except Exception as e:
            logger.error(f"创建数据库时发生未知错误: {e}")
            return False
    
    def setup_database(self) -> bool:
        """设置数据库环境"""
        try:
            # 检查PostgreSQL是否已安装
            if not self.check_postgres_installed():
                logger.error("PostgreSQL未安装，请先安装PostgreSQL")
                logger.info("安装指南:")
                if self.system == "darwin":
                    logger.info("  macOS: brew install postgresql")
                elif self.system == "linux":
                    logger.info("  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib")
                    logger.info("  CentOS/RHEL: sudo yum install postgresql postgresql-server")
                elif self.system == "windows":
                    logger.info("  Windows: 下载并安装 https://www.postgresql.org/download/windows/")
                return False
            
            # 检查PostgreSQL是否正在运行
            if self.check_postgres_running():
                logger.info("PostgreSQL服务正在运行")
                self.postgres_running = True
            else:
                logger.info("PostgreSQL服务未运行，尝试启动...")
                if self.start_postgres_service():
                    # 等待服务启动
                    for i in range(10):
                        time.sleep(2)
                        if self.check_postgres_running():
                            logger.info("PostgreSQL服务启动成功")
                            self.postgres_running = True
                            break
                    else:
                        logger.error("PostgreSQL服务启动超时")
                        return False
                else:
                    logger.error("无法启动PostgreSQL服务")
                    return False
            
            # 创建数据库（如果不存在）
            if not self.create_database_if_not_exists():
                return False
            
            logger.info("数据库环境设置完成")
            return True
            
        except Exception as e:
            logger.error(f"设置数据库环境时发生错误: {e}")
            return False
    
    def stop_postgres_service(self) -> bool:
        """停止PostgreSQL服务"""
        try:
            if self.system == "darwin":  # macOS
                result = subprocess.run(["brew", "services", "stop", "postgresql"], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务停止成功")
                    return True
            elif self.system == "linux":
                service_name = self.get_postgres_service_name()
                result = subprocess.run(["sudo", "systemctl", "stop", service_name], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务停止成功")
                    return True
            elif self.system == "windows":
                result = subprocess.run(["net", "stop", "postgresql"], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    logger.info("PostgreSQL服务停止成功")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"停止PostgreSQL服务时发生错误: {e}")
            return False
