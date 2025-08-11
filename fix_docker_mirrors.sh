#!/bin/bash

# Docker Registry Mirrors 配置脚本
echo "正在配置Docker Registry Mirrors..."

# 检查Docker Desktop是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker Desktop未运行，请先启动Docker Desktop"
    exit 1
fi

# 配置文件路径
CONFIG_FILE="$HOME/Library/Group Containers/group.com.docker/settings.json"

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: Docker配置文件不存在: $CONFIG_FILE"
    echo "请确保Docker Desktop已正确安装"
    exit 1
fi

# 备份原配置文件
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "已备份原配置文件"

# 创建新的配置（包含常用的中国镜像源）
cat > "$CONFIG_FILE" << 'EOF'
{
  "registryMirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://registry.docker-cn.com"
  ],
  "insecureRegistries": [],
  "debug": false,
  "experimental": false,
  "features": {
    "buildkit": true
  },
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "dns": [],
  "stackOrchestrator": "swarm"
}
EOF

echo "已更新Docker配置文件"
echo "请重启Docker Desktop以使配置生效"

# 显示当前配置
echo "当前Registry Mirrors配置:"
docker info | grep -A 10 "Registry Mirrors" || echo "需要重启Docker Desktop后查看"

echo "配置完成！请重启Docker Desktop。"
