# 合约交易数据同步工具

这个工具用于从以太坊区块链获取指定合约的交易数据并存储到PostgreSQL数据库中。

## 功能特性

- 自动检测和启动PostgreSQL数据库服务
- 支持代理合约和普通合约的交易数据获取
- **自动分页处理**：支持Etherscan API分页，自动获取所有交易数据
- 批量同步历史交易数据
- 实时监控新区块
- 完善的异常处理和日志记录

## 系统要求

- Python 3.7+
- PostgreSQL 12+
- 以太坊RPC节点访问权限
- Etherscan API密钥

## 安装步骤

### 1. 安装PostgreSQL

#### 自动安装（推荐）
```bash
python install_postgresql.py
```

#### 手动安装

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**CentOS/RHEL:**
```bash
sudo yum install postgresql postgresql-server
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. 设置PostgreSQL用户和数据库

```bash
# 设置postgres用户密码
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'password';"

# 创建数据库
sudo -u postgres psql -c "CREATE DATABASE ethereum_transactions;"

# 授权
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ethereum_transactions TO postgres;"
```

### 3. 安装Python依赖

```bash
pip install psycopg2-binary requests web3
```

## 使用方法

### 基本用法

```bash
python slither/tools/contract_abstract/transaction_service.py \
    --meta-path /path/to/meta.json \
    --rpc-url https://mainnet.infura.io/v3/YOUR_PROJECT_ID \
    --etherscan-apikey YOUR_ETHERSCAN_API_KEY
```

### 自定义数据库配置

```bash
python slither/tools/contract_abstract/transaction_service.py \
    --meta-path /path/to/meta.json \
    --rpc-url https://mainnet.infura.io/v3/YOUR_PROJECT_ID \
    --etherscan-apikey YOUR_ETHERSCAN_API_KEY \
    --db-host localhost \
    --db-port 5432 \
    --db-name ethereum_transactions \
    --db-user postgres \
    --db-password your_password
```

## 参数说明

### 必需参数
- `--meta-path`: 元数据文件路径，包含合约地址等信息
- `--rpc-url`: 以太坊RPC节点URL
- `--etherscan-apikey`: Etherscan API密钥

### 可选参数
- `--db-host`: 数据库主机地址（默认: localhost）
- `--db-port`: 数据库端口（默认: 5432）
- `--db-name`: 数据库名称（默认: ethereum_transactions）
- `--db-user`: 数据库用户名（默认: postgres）
- `--db-password`: 数据库密码（默认: password）

## 元数据文件格式

```json
{
  "contract_name": {
    "address": "0x...",
    "logic_address": "0x..."  // 可选，代理合约的逻辑地址
  }
}
```

## 数据库表结构

工具会自动创建以下表结构：

```sql
CREATE TABLE ethereum_transactions_{contract_address} (
    block_hash VARCHAR(66) PRIMARY KEY,
    block_number BIGINT,
    time_stamp BIGINT,
    hash VARCHAR(66) UNIQUE,
    nonce BIGINT,
    transaction_index INTEGER,
    from_address VARCHAR(42),
    to_address VARCHAR(42),
    value NUMERIC(65,0),
    gas BIGINT,
    gas_price BIGINT,
    input_data TEXT,
    method_id VARCHAR(10),
    function_name TEXT,
    contract_address VARCHAR(42),
    cumulative_gas_used BIGINT,
    tx_receipt_status INTEGER,
    gas_used BIGINT,
    confirmations BIGINT,
    is_error INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 日志文件

程序运行时会生成以下日志文件：
- `transaction_service.log`: 主程序日志
- 控制台输出: 实时运行状态

## 故障排除

### 数据库连接失败

1. 确保PostgreSQL服务正在运行
2. 检查数据库配置参数是否正确
3. 验证用户名和密码
4. 确认数据库已创建

### API请求失败

1. 检查Etherscan API密钥是否有效
2. 确认网络连接正常
3. 检查API使用配额是否超限

### 权限问题

1. 确保有足够的权限启动数据库服务
2. 检查文件读写权限
3. 验证数据库用户权限

## 注意事项

- 首次运行时会自动创建数据库和表结构
- 程序会从合约部署区块开始同步历史数据
- 实时监控模式下会持续运行直到手动停止
- 建议在生产环境中使用更安全的数据库密码
- **分页处理**：程序会自动处理Etherscan API的分页限制，每页最多10000条记录
- **API限流**：程序包含API限流保护，在请求间添加延迟避免触发限制

## 许可证

MIT License
