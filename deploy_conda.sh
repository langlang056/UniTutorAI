#!/bin/bash
# PPT Helper Conda 环境部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  PPT Helper 部署脚本 (Conda 版)${NC}"
echo -e "${GREEN}========================================${NC}\n"

# 检查是否为 root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}请使用 sudo 运行此脚本${NC}"
   exit 1
fi

ACTUAL_USER=${SUDO_USER:-$USER}
echo -e "${YELLOW}当前用户: $ACTUAL_USER${NC}\n"

# 配置变量
read -p "请输入你的服务器 IP 地址或域名: " SERVER_IP
read -p "请输入你的 Google Gemini API Key: " GEMINI_API_KEY
read -p "请输入项目路径: " INSTALL_PATH
read -p "请输入 conda 环境名称 (例: ppt-helper): " CONDA_ENV
read -p "请输入 conda Python 路径 (运行 'which python' 获取): " PYTHON_PATH

INSTALL_PATH="${INSTALL_PATH/#\~/$HOME}"
echo -e "${GREEN}项目路径: $INSTALL_PATH${NC}"
echo -e "${GREEN}Python 路径: $PYTHON_PATH${NC}\n"

echo -e "${GREEN}开始部署...${NC}\n"

# 1. 检查 Python 版本
echo -e "${YELLOW}[1/8] 检查 Python 环境...${NC}"
PYTHON_VERSION=$($PYTHON_PATH --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"

# 2. 检查项目目录
echo -e "${YELLOW}[2/8] 检查项目目录...${NC}"
if [ ! -d "$INSTALL_PATH" ]; then
    echo -e "${RED}错误: 项目目录不存在: $INSTALL_PATH${NC}"
    exit 1
fi
cd "$INSTALL_PATH"
chown -R $ACTUAL_USER:$ACTUAL_USER "$INSTALL_PATH"

# 3. 安装系统依赖
echo -e "${YELLOW}[3/8] 安装系统依赖...${NC}"
apt update
apt install -y nginx git curl wget vim build-essential

# 检查 Node.js 版本
CURRENT_NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$CURRENT_NODE_VERSION" ] || [ "$CURRENT_NODE_VERSION" -lt 18 ]; then
    echo -e "${YELLOW}当前 Node.js 版本过旧，安装 Node.js 18...${NC}"
    
    # 移除旧版本
    apt remove -y nodejs npm
    
    # 安装 Node.js 18
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt install -y nodejs
    
    echo -e "${GREEN}✓ Node.js 版本: $(node -v)${NC}"
    echo -e "${GREEN}✓ npm 版本: $(npm -v)${NC}"
else
    echo -e "${GREEN}✓ Node.js 版本已满足要求: v${CURRENT_NODE_VERSION}${NC}"
fi

# 4. 配置后端
echo -e "${YELLOW}[4/8] 配置后端...${NC}"
cd "$INSTALL_PATH/backend"

# 检查依赖是否已安装
if sudo -u $ACTUAL_USER $PYTHON_PATH -c "import fastapi" 2>/dev/null; then
    echo -e "${GREEN}Python 依赖已安装，跳过...${NC}"
else
    echo -e "${YELLOW}安装 Python 依赖...${NC}"
    sudo -u $ACTUAL_USER $PYTHON_PATH -m pip install -r requirements.txt
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

mkdir -p uploads temp
chown -R $ACTUAL_USER:$ACTUAL_USER uploads temp
chmod -R 755 uploads temp

# 5. 配置前端
echo -e "${YELLOW}[5/8] 配置前端...${NC}"
cd "$INSTALL_PATH/frontend"

cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://$SERVER_IP/api
EOF

if [ ! -d "node_modules" ]; then
    sudo -u $ACTUAL_USER npm install
fi
sudo -u $ACTUAL_USER npm run build

# 6. 创建后端服务
echo -e "${YELLOW}[6/8] 创建后端服务...${NC}"

UVICORN_PATH=$(dirname $PYTHON_PATH)/uvicorn
if [ ! -f "$UVICORN_PATH" ]; then
    echo -e "${YELLOW}未找到 uvicorn，尝试查找...${NC}"
    UVICORN_PATH=$(sudo -u $ACTUAL_USER which uvicorn 2>/dev/null || echo "")
    if [ -z "$UVICORN_PATH" ]; then
        echo -e "${RED}错误: 找不到 uvicorn${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ uvicorn 路径: $UVICORN_PATH${NC}"

cat > /etc/systemd/system/ppt-helper-backend.service << EOF
[Unit]
Description=PPT Helper Backend Service
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_PATH/backend
Environment="PATH=$(dirname $PYTHON_PATH):/usr/bin:/bin"
ExecStart=$UVICORN_PATH app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. 创建前端服务
echo -e "${YELLOW}[7/8] 创建前端服务...${NC}"
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

# 8. 配置 Nginx
echo -e "${YELLOW}[8/8] 配置 Nginx...${NC}"
cat > /etc/nginx/sites-available/ppt-helper << EOF
server {
    listen 80;
    server_name $SERVER_IP;

    client_max_body_size 50M;

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

ln -sf /etc/nginx/sites-available/ppt-helper /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t

# 9. 启动服务
echo -e "${YELLOW}[9/8] 启动服务...${NC}"
systemctl daemon-reload
systemctl start ppt-helper-backend
systemctl start ppt-helper-frontend
systemctl restart nginx

systemctl enable ppt-helper-backend
systemctl enable ppt-helper-frontend
systemctl enable nginx

# 检查状态
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}服务状态:${NC}"
systemctl status ppt-helper-backend --no-pager | head -n 5
echo ""
systemctl status ppt-helper-frontend --no-pager | head -n 5

echo -e "\n${GREEN}访问地址: http://$SERVER_IP${NC}"
echo -e "${GREEN}API 文档: http://$SERVER_IP:8000/docs${NC}\n"

echo -e "${YELLOW}常用命令:${NC}"
echo -e "  查看后端日志: ${GREEN}sudo journalctl -u ppt-helper-backend -f${NC}"
echo -e "  查看前端日志: ${GREEN}sudo journalctl -u ppt-helper-frontend -f${NC}"
echo -e "  重启后端: ${GREEN}sudo systemctl restart ppt-helper-backend${NC}"
echo -e "  重启前端: ${GREEN}sudo systemctl restart ppt-helper-frontend${NC}\n"
