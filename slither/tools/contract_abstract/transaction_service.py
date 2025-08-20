import json
import time
import logging
import sys
from typing import Optional
from argparse import ArgumentParser
from slither.tools.contract_abstract.onchain.contract_info import ContractInfo
from slither.tools.contract_abstract.onchain.transaction_info import TransactionInfo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def parse_args():
    parser = ArgumentParser(description="获取合约交易信息")
    parser.add_argument("--meta-path", required=True, action="store", help="元数据文件路径")
    parser.add_argument("--rpc-url", required=True, action="store", help="以太坊RPC URL")
    parser.add_argument("--etherscan-apikey", required=True, action="store", help="Etherscan API密钥")
    
    # 数据库配置参数
    parser.add_argument("--db-host", default="localhost", help="数据库主机地址")
    parser.add_argument("--db-port", type=int, default=5432, help="数据库端口")
    parser.add_argument("--db-name", default="ethereum_transactions", help="数据库名称")
    parser.add_argument("--db-user", default="postgres", help="数据库用户名")
    parser.add_argument("--db-password", default="password", help="数据库密码")
    
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    transaction_info = None
    contract_info = None
    
    try:
        # 读取元数据文件
        logger.info("开始读取元数据文件...")
        with open(args.meta_path, "r") as f:
            meta_json = json.load(f)
        logger.info(f"成功读取元数据文件: {args.meta_path}")

        meta_json = meta_json[list(meta_json.keys())[0]]

        # 初始化合约信息
        logger.info("初始化合约信息...")
        contract_info = ContractInfo(args.rpc_url)
        logger.info("合约信息初始化成功")

        # 构建数据库配置
        db_config = {
            'host': args.db_host,
            'port': args.db_port,
            'database': args.db_name,
            'user': args.db_user,
            'password': args.db_password
        }
        logger.info(f"数据库配置: {args.db_host}:{args.db_port}/{args.db_name}")

        # 初始化交易信息
        logger.info("初始化交易信息...")
        if meta_json.get("logic_address"):
            transaction_info = TransactionInfo(
                meta_json["address"], 
                args.etherscan_apikey, 
                contract_info, 
                db_config=db_config,
                logic_address=meta_json["logic_address"]
            )
            logger.info(f"使用代理合约模式，逻辑地址: {meta_json['logic_address']}")
        else:
            transaction_info = TransactionInfo(
                meta_json["address"], 
                args.etherscan_apikey, 
                contract_info,
                db_config=db_config
            )
            logger.info("使用普通合约模式")
        logger.info("交易信息初始化成功")

        # 获取区块信息
        logger.info("获取区块信息...")
        local_latest_block = transaction_info.get_latest_block_number()
        if local_latest_block is None:
            logger.warning("无法获取本地最新区块号，使用0作为起始区块")
            return
        
        etherscan_latest_block = transaction_info.get_etherscan_latest_block()
        if etherscan_latest_block is None:
            logger.error("无法获取Etherscan最新区块号，程序退出")
            return
        
        deployment_block = transaction_info.get_contract_creation_block()
        if deployment_block is None:
            logger.warning("无法获取合约部署区块号，使用0作为部署区块")
            return

        start_block = max(local_latest_block, deployment_block)
        end_block = etherscan_latest_block
        
        logger.info(f"同步范围: {start_block} - {end_block}")
        logger.info(f"本地最新区块: {local_latest_block}")
        logger.info(f"Etherscan最新区块: {etherscan_latest_block}")
        logger.info(f"合约部署区块: {deployment_block}")

        # 先同步到最新区块，每次获取最多100000个区块的该合约的交易
        every_batch_block = 5000
        logger.info(f"开始批量同步，每批处理 {every_batch_block} 个区块")
        
        for i in range(start_block, end_block, every_batch_block):
            try:
                current_end = min(i + every_batch_block, end_block)
                logger.info(f"处理区块范围: {i} - {current_end}")
                
                txs = transaction_info.get_transactions_from_etherscan(i, current_end)
                if txs:
                    saved_count = transaction_info.save_transactions_to_db(txs)
                    logger.info(f"成功保存 {saved_count} 条交易记录")
                else:
                    logger.info(f"区块范围 {i} - {current_end} 中没有找到交易")
                    
            except Exception as e:
                logger.error(f"处理区块范围 {i} - {current_end} 时发生错误: {e}")
                raise Exception(f"处理区块范围 {i} - {current_end} 时发生错误: {e}")

        # 然后每12s查询一次最新区块，如果最新区块大于end_block，则继续获取该合约的交易
        logger.info("开始监控新区块...")
        consecutive_errors = 0
        max_consecutive_errors = 5
        time_interval = 12
        
        while True:
            try:
                time.sleep(time_interval)
                etherscan_latest_block = transaction_info.get_etherscan_latest_block()
                
                if etherscan_latest_block is None:
                    consecutive_errors += 1
                    logger.error(f"无法获取Etherscan最新区块号 (错误次数: {consecutive_errors})")
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"连续 {max_consecutive_errors} 次获取失败，程序退出")
                        break
                    continue
                
                consecutive_errors = 0  # 重置错误计数
                
                if etherscan_latest_block > end_block:
                    logger.info(f"发现新区块: {etherscan_latest_block}，开始同步...")
                    try:
                        txs = transaction_info.get_transactions_from_etherscan(end_block, etherscan_latest_block)
                        if txs:
                            saved_count = transaction_info.save_transactions_to_db(txs)
                            logger.info(f"成功保存 {saved_count} 条新区块交易记录")
                        else:
                            logger.info(f"新区块范围 {end_block} - {etherscan_latest_block} 中没有找到交易")
                    except Exception as e:
                        logger.error(f"同步新区块时发生错误: {e}")
                        continue
                    
                    end_block = etherscan_latest_block
                else:
                    logger.debug(f"当前最新区块: {etherscan_latest_block}，无需同步")
                    
            except KeyboardInterrupt:
                logger.info("收到中断信号，程序正在退出...")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"监控过程中发生未知错误: {e} (错误次数: {consecutive_errors})")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"连续 {max_consecutive_errors} 次发生错误，程序退出")
                    break
                continue

    except FileNotFoundError:
        logger.error(f"元数据文件不存在: {args.meta_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"元数据文件格式错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序初始化失败: {e}")
        sys.exit(1)
    finally:
        # 清理资源
        if transaction_info:
            try:
                transaction_info.close_db_connection()
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接时发生错误: {e}")

if __name__ == "__main__":
    main()