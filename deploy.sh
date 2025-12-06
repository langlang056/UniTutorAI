#!/bin/bash
# PPT Helper 一键部署脚本 (Ubuntu/Debian)

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  PPT Helper 自动部署脚本${NC}"
echo -e "${GREEN}========================================${NC}\n"

# 检查是否为 root 用户
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}请使用 sudo 运行此脚本${NC}"
   exit 1
fi

# 获取实际用户名（即使使用 sudo）
ACTUAL_USER=${SUDO_USER:-$USER}
echo -e "${YELLOW}当前用户: $ACTUAL_USER${NC}\n"

# 配置变量
read -p "请输入你的服务器 IP 地址或域名 (例: 192.168.1.100): " SERVER_IP
read -p "请输入你的 Google Gemini API Key: " GEMINI_API_KEY
read -p "请输入项目安装路径 (默认: /opt/ppt_helper): " INSTALL_PATH
INSTALL_PATH=${INSTALL_PATH:-/opt/ppt_helper}

echo -e "\n${GREEN}开始部署...${NC}\n"

# 1. 检测 Python 环境
echo -e "${YELLOW}[1/9] 检测 Python 环境...${NC}"

# 检测是否在 conda 环境中
if command -v conda &> /dev/null && [ ! -z "$CONDA_DEFAULT_ENV" ]; then
    echo -e "${GREEN}✓ 检测到 conda 环境: $CONDA_DEFAULT_ENV${NC}"
    PYTHON_CMD=$(which python)
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"
    USE_CONDA=true
else
    echo -e "${YELLOW}未检测到 conda 环境，将使用系统 Python${NC}"
    USE_CONDA=false
    
    # 安装系统依赖
    apt update
    
    # 尝试安装 Python 3.11，如果失败则使用系统默认 Python
    if apt-cache show python3.11 > /dev/null 2>&1; then
        apt install -y python3.11 python3.11-venv python3-pip
        PYTHON_CMD=python3.11
    else
        echo -e "${YELLOW}Python 3.11 不可用，使用系统默认 Python 3${NC}"
        apt install -y python3 python3-venv python3-pip
        PYTHON_CMD=python3
    fi
fi

# 安装其他系统依赖
apt install -y nodejs npm nginx git curl wget vim build-essential

echo -e "${GREEN}✓ 将使用 Python: $PYTHON_CMD${NC}"

# 2. 检查项目目录
echo -e "${YELLOW}[2/9] 检查项目目录...${NC}"
if [ ! -d "$INSTALL_PATH" ]; then
    echo -e "${RED}错误: 项目目录不存在: $INSTALL_PATH${NC}"
    echo -e "${YELLOW}请先将项目文件上传到该目录${NC}"
    exit 1
fi

cd "$INSTALL_PATH"
chown -R $ACTUAL_USER:$ACTUAL_USER "$INSTALL_PATH"

# 3. 配置后端
echo -e "${YELLOW}[3/9] 配置后端...${NC}"
cd "$INSTALL_PATH/backend"

# 如果使用 conda，直接安装依赖；否则创建虚拟环境
if [ "$USE_CONDA" = true ]; then
    echo -e "${GREEN}使用 conda 环境安装后端依赖...${NC}"
    pip install -r requirements.txt
else
    echo -e "${GREEN}创建虚拟环境...${NC}"
    sudo -u $ACTUAL_USER $PYTHON_CMD -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# 创建 .env 文件
cat > .env << EOF
GOOGLE_API_KEY=$GEMINI_API_KEY
HOST=0.0.0.0
PORT=8000
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./ppt_helper.db
UPLOAD_DIR=uploads
TEMP_DIR=temp
MAX_FILE_SIZE_MB=50
EOF

# 创建必要目录
mkdir -p uploads temp
chown -R $ACTUAL_USER:$ACTUAL_USER uploads temp
chmod -R 755 uploads temp

# 4. 配置前端
echo -e "${YELLOW}[4/9] 配置前端...${NC}"
cd "$INSTALL_PATH/frontend"

# 创建 .env.local
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://$SERVER_IP/api
EOF

# 安装依赖并构建
sudo -u $ACTUAL_USER npm install
sudo -u $ACTUAL_USER npm run build

# 5. 创建后端服务
echo -e "${YELLOW}[5/9] 创建后端服务...${NC}"

# 确定 uvicorn 路径
if [ "$USE_CONDA" = true ]; then
    UVICORN_PATH=$(which uvicorn)
    PYTHON_ENV_PATH=$(dirname $(which python))
else
    UVICORN_PATH="$INSTALL_PATH/backend/venv/bin/uvicorn"
    PYTHON_ENV_PATH="$INSTALL_PATH/backend/venv/bin"
fi

cat > /etc/systemd/system/ppt-helper-backend.service << EOF
[Unit]
Description=PPT Helper Backend Service
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_PATH/backend
Environment="PATH=$PYTHON_ENV_PATH:/usr/bin:/bin"
ExecStart=$UVICORN_PATH app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. 创建前端服务
echo -e "${YELLOW}[6/9] 创建前端服务...${NC}"
cat > /etc/systemd/system/ppt-helper-frontend.service << EOF
[Unit]
Description=PPT Helper Frontend Service
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_PATH/frontend
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. 配置 Nginx
echo -e "${YELLOW}[7/9] 配置 Nginx...${NC}"
cat > /etc/nginx/sites-available/ppt-helper << EOF
server {
    listen 80;
    server_name $SERVER_IP;

    client_max_body_size 50M;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 后端 API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 文档 API
    location /docs {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

# 启用站点
ln -sf /etc/nginx/sites-available/ppt-helper /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试 Nginx 配置
nginx -t

# 8. 启动所有服务
echo -e "${YELLOW}[8/9] 启动服务...${NC}"
systemctl daemon-reload

systemctl start ppt-helper-backend
systemctl start ppt-helper-frontend
systemctl restart nginx

systemctl enable ppt-helper-backend
systemctl enable ppt-helper-frontend
systemctl enable nginx

# 9. 配置防火墙
echo -e "${YELLOW}[9/9] 配置防火墙...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo -e "${GREEN}防火墙规则已添加${NC}"
fi

# 检查服务状态
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}服务状态:${NC}"
systemctl status ppt-helper-backend --no-pager | head -n 5
echo ""
systemctl status ppt-helper-frontend --no-pager | head -n 5
echo ""
systemctl status nginx --no-pager | head -n 5

echo -e "\n${GREEN}访问地址: http://$SERVER_IP${NC}"
echo -e "${GREEN}API 文档: http://$SERVER_IP:8000/docs${NC}\n"

echo -e "${YELLOW}常用命令:${NC}"
echo -e "  查看后端日志: ${GREEN}sudo journalctl -u ppt-helper-backend -f${NC}"
echo -e "  查看前端日志: ${GREEN}sudo journalctl -u ppt-helper-frontend -f${NC}"
echo -e "  重启后端: ${GREEN}sudo systemctl restart ppt-helper-backend${NC}"
echo -e "  重启前端: ${GREEN}sudo systemctl restart ppt-helper-frontend${NC}"
echo -e "  重启 Nginx: ${GREEN}sudo systemctl restart nginx${NC}\n"

echo -e "${YELLOW}如果无法访问，请检查:${NC}"
echo -e "  1. 云服务器安全组是否开放了 80 端口"
echo -e "  2. 防火墙是否允许 80 端口: ${GREEN}sudo ufw status${NC}"
echo -e "  3. 服务是否正常运行: ${GREEN}sudo systemctl status ppt-helper-backend${NC}\n"
