# Etherscan交易数据PostgreSQL存储系统

这个系统用于从Etherscan API获取以太坊交易数据并将其存储到PostgreSQL数据库中。

## 功能特性

- 🔍 从Etherscan API获取交易数据
- 💾 将交易数据存储到PostgreSQL数据库
- 📊 支持按地址、区块范围等条件查询
- 🔄 自动处理重复数据（基于区块哈希）
- ⚡ 高性能索引优化
- 🛡️ 错误处理和事务回滚

## 安装依赖

```bash
pip install -r requirements.txt
```

## 数据库设置

### 1. 安装PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Windows
# 从 https://www.postgresql.org/download/windows/ 下载安装包
```

### 2. 创建数据库

```sql
CREATE DATABASE ethereum_transactions;
CREATE USER ethereum_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ethereum_transactions TO ethereum_user;
```

## 配置

### 环境变量

创建 `.env` 文件：

```env
# Etherscan API密钥
ETHERSCAN_API_KEY=your_etherscan_api_key_here

# PostgreSQL数据库配置
DB_HOST=localhost
DB_NAME=ethereum_transactions
DB_USER=ethereum_user
DB_PASSWORD=your_password
DB_PORT=5432
```

### 获取Etherscan API密钥

1. 访问 [Etherscan](https://etherscan.io/)
2. 注册账户并登录
3. 进入 [API-KEYs](https://etherscan.io/myapikey) 页面
4. 创建新的API密钥

## 使用方法

### 基本使用

```python
from transaction_info import TransactionInfo

# 配置
ETHERSCAN_API_KEY = "your_api_key"
DB_CONFIG = {
    'host': 'localhost',
    'database': 'ethereum_transactions',
    'user': 'ethereum_user',
    'password': 'your_password',
    'port': 5432
}

# 创建实例
tx_info = TransactionInfo(
    etherscan_api_key=ETHERSCAN_API_KEY,
    contract_info=your_contract_info,  # 需要提供实际的contract_info对象
    db_config=DB_CONFIG
)

# 连接数据库并创建表
tx_info.connect_db()
tx_info.create_tables()

# 保存交易数据
transaction_data = {
    'blockNumber': '23100743',
    'blockHash': '0xa0ed0d8104100967d979d13e36d45515d0ed9adfc82daf59205d35d1adad7a04',
    'timeStamp': '1754709239',
    'hash': '0xbf4692d8030bad74f1fd0e05224480237ae3f5239e261e45aa734bd8c91c096f',
    'nonce': '2318',
    'transactionIndex': '183',
    'from': '0x0a0ae914771ec0a5851049864ccc27b1baa8cd43',
    'to': '0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2',
    'value': '0',
    'gas': '300000',
    'gasPrice': '282232339',
    'input': '0x573ade81000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec70000000000000000000000000000000000000000000000000000000708ea1b7800000000000000000000000000000000000000000000000000000000000000020000000000000000000000000a0ae914771ec0a5851049864ccc27b1baa8cd43',
    'methodId': '0x573ade81',
    'functionName': 'repay(address _owner, uint256 _pid, uint256 _amount, address _payer)',
    'contractAddress': '',
    'cumulativeGasUsed': '20184909',
    'txreceipt_status': '1',
    'gasUsed': '161175',
    'confirmations': '42276',
    'isError': '0'
}

# 保存单条交易
success = tx_info.save_single_transaction(transaction_data)

# 保存多条交易
transactions = [transaction_data, ...]  # 多条交易数据
saved_count = tx_info.save_transactions_to_db(transactions)

# 查询交易数据
transactions = tx_info.get_transactions_from_db(
    address='0x0a0ae914771ec0a5851049864ccc27b1baa8cd43',
    start_block=23100740,
    end_block=23100750,
    limit=100
)

# 获取最新区块信息
latest_block = tx_info.get_latest_block_number()
print(f"最新区块号: {latest_block}")

latest_info = tx_info.get_latest_block_info()
if latest_info:
    print(f"最新区块包含 {latest_info['transaction_count']} 笔交易")

block_range = tx_info.get_block_range()
if block_range:
    print(f"区块范围: {block_range['min_block']} - {block_range['max_block']}")

# 关闭连接
tx_info.close_db_connection()

### 运行示例

```bash
python example_usage.py
```

## 重要变更说明

### 主键变更
- **旧版本**: 使用自增ID (`id SERIAL`) 作为主键
- **新版本**: 使用区块哈希 (`block_hash`) 作为主键
- **原因**: 区块哈希在以太坊中是唯一的，更适合作为主键，可以防止重复数据插入
- **影响**: 如果之前有数据，需要重新创建表结构

## 数据库表结构

### ethereum_transactions 表

| 字段名 | 类型 | 说明 |
|--------|------|------|
| block_hash | VARCHAR(66) | **主键**，区块哈希 |
| block_number | BIGINT | 区块号 |
| time_stamp | BIGINT | 时间戳 |
| hash | VARCHAR(66) | 交易哈希（唯一） |
| nonce | BIGINT | 随机数 |
| transaction_index | INTEGER | 交易在区块中的索引 |
| from_address | VARCHAR(42) | 发送方地址 |
| to_address | VARCHAR(42) | 接收方地址 |
| value | NUMERIC(65,0) | 交易价值 |
| gas | BIGINT | Gas限制 |
| gas_price | BIGINT | Gas价格 |
| input_data | TEXT | 输入数据 |
| method_id | VARCHAR(10) | 方法ID |
| function_name | TEXT | 函数名 |
| contract_address | VARCHAR(42) | 合约地址 |
| cumulative_gas_used | BIGINT | 累计Gas使用量 |
| tx_receipt_status | INTEGER | 交易收据状态 |
| gas_used | BIGINT | Gas使用量 |
| confirmations | BIGINT | 确认数 |
| is_error | INTEGER | 是否错误 |
| created_at | TIMESTAMP | 创建时间 |

### 索引

- **主键索引**: `block_hash` (自动创建)
- `idx_transactions_hash`: 交易哈希索引
- `idx_transactions_block_number`: 区块号索引
- `idx_transactions_from_address`: 发送方地址索引
- `idx_transactions_to_address`: 接收方地址索引
- `idx_transactions_time_stamp`: 时间戳索引

## API方法说明

### TransactionInfo 类方法

#### `connect_db()`
连接到PostgreSQL数据库

#### `create_tables()`
创建数据库表和索引

#### `save_single_transaction(transaction)`
保存单条交易数据
- **参数**: `transaction` (Dict) - 交易数据字典
- **返回**: `bool` - 是否保存成功

#### `save_transactions_to_db(transactions)`
批量保存交易数据
- **参数**: `transactions` (List[Dict]) - 交易数据列表
- **返回**: `int` - 成功保存的记录数

#### `get_transactions_from_db(address=None, start_block=None, end_block=None, limit=100)`
从数据库查询交易数据
- **参数**:
  - `address` (str, 可选) - 地址过滤
  - `start_block` (int, 可选) - 起始区块号
  - `end_block` (int, 可选) - 结束区块号
  - `limit` (int) - 查询限制数量
- **返回**: `List[Dict]` - 交易数据列表

#### `get_latest_block_number()`
获取当前存储的交易中最新的区块号
- **返回**: `Optional[int]` - 最新区块号，如果没有数据则返回None

#### `get_latest_block_info()`
获取最新区块的详细信息
- **返回**: `Optional[Dict[str, Any]]` - 包含区块号、区块哈希、时间戳、交易数量等信息的字典

#### `get_block_range()`
获取数据库中区块的范围（最小和最大区块号）
- **返回**: `Optional[Dict[str, int]]` - 包含最小区块号、最大区块号、总区块数的字典

#### `close_db_connection()`
关闭数据库连接

## 错误处理

系统包含完善的错误处理机制：

- 数据库连接失败处理
- 事务回滚机制
- 重复数据自动跳过
- API请求异常处理

## 性能优化

- 使用批量插入提高性能
- 创建合适的数据库索引
- 使用 `ON CONFLICT DO NOTHING` 避免重复插入
- 连接池管理

## 注意事项

1. **API限制**: Etherscan API有请求频率限制，请合理使用
2. **数据量**: 大量数据存储时注意磁盘空间
3. **备份**: 定期备份重要数据
4. **监控**: 监控数据库性能和存储空间

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查数据库服务是否运行
   - 验证连接参数是否正确
   - 确认用户权限

2. **API请求失败**
   - 检查API密钥是否有效
   - 确认网络连接正常
   - 查看API使用限制

3. **数据插入失败**
   - 检查数据格式是否正确
   - 确认表结构是否匹配
   - 查看错误日志

## 许可证

MIT License
