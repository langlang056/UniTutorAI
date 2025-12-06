# Linux 服务器部署指南

本指南将帮助你把 PPT Helper 部署到 Linux 服务器上，通过 IP 地址访问。

## 📋 部署前准备

### 1. 服务器要求
- Ubuntu 20.04+ / CentOS 7+ 或其他 Linux 发行版
- Python 3.11+
- Node.js 18+
- Nginx
- 至少 2GB RAM
- 10GB 可用磁盘空间

### 2. 域名或 IP
- 假设你的服务器 IP 是: `192.168.1.100`（替换成你的实际 IP）
- 如果有域名，也可以使用域名

---

## 🚀 部署步骤

### 步骤 1: 安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget vim build-essential

# 安装 Nginx
sudo apt install -y nginx

# 安装 Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# 安装 Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 验证安装
python3.11 --version
node --version
npm --version
nginx -v
```

### 步骤 2: 上传项目文件

```bash
# 方式 1: 使用 Git
cd /opt
sudo git clone <your-repo-url> ppt_helper
sudo chown -R $USER:$USER /opt/ppt_helper

# 方式 2: 使用 scp 从本地上传
# 在本地机器上运行:
# scp -r /path/to/ppt_helper user@192.168.1.100:/opt/

# 进入项目目录
cd /opt/ppt_helper
```

### 步骤 3: 配置后端

```bash
cd /opt/ppt_helper/backend

# 创建 Python 虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建环境变量文件
cat > .env << 'EOF'
# Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./ppt_helper.db

# 上传配置
UPLOAD_DIR=uploads
TEMP_DIR=temp
MAX_FILE_SIZE_MB=50
EOF

# 编辑 .env，填入你的实际 API Key
vim .env

# 创建必要目录
mkdir -p uploads temp

# 测试后端启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Ctrl+C 停止测试
```

### 步骤 4: 配置前端

```bash
cd /opt/ppt_helper/frontend

# 创建环境变量文件
cat > .env.local << 'EOF'
# 后端 API 地址（使用服务器 IP）
NEXT_PUBLIC_API_URL=http://192.168.1.100:8000
EOF

# 替换成你的实际 IP
vim .env.local

# 安装依赖
npm install

# 构建生产版本
npm run build

# 测试前端启动
npm run start
# Ctrl+C 停止测试
```

### 步骤 5: 配置 Systemd 服务（保持后台运行）

#### 5.1 创建后端服务

```bash
sudo tee /etc/systemd/system/ppt-helper-backend.service > /dev/null << 'EOF'
[Unit]
Description=PPT Helper Backend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ppt_helper/backend
Environment="PATH=/opt/ppt_helper/backend/venv/bin"
ExecStart=/opt/ppt_helper/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 替换 User 为你的实际用户名
sudo vim /etc/systemd/system/ppt-helper-backend.service
```

#### 5.2 创建前端服务

```bash
sudo tee /etc/systemd/system/ppt-helper-frontend.service > /dev/null << 'EOF'
[Unit]
Description=PPT Helper Frontend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ppt_helper/frontend
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 替换 User 为你的实际用户名
sudo vim /etc/systemd/system/ppt-helper-frontend.service
```

#### 5.3 启动服务

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start ppt-helper-backend
sudo systemctl start ppt-helper-frontend

# 设置开机自启
sudo systemctl enable ppt-helper-backend
sudo systemctl enable ppt-helper-frontend

# 检查服务状态
sudo systemctl status ppt-helper-backend
sudo systemctl status ppt-helper-frontend

# 查看日志
sudo journalctl -u ppt-helper-backend -f
sudo journalctl -u ppt-helper-frontend -f
```

### 步骤 6: 配置 Nginx 反向代理

```bash
sudo tee /etc/nginx/sites-available/ppt-helper > /dev/null << 'EOF'
server {
    listen 80;
    server_name 192.168.1.100;  # 替换为你的服务器 IP 或域名

    client_max_body_size 50M;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 文档 API
    location /docs {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# 编辑配置，替换 IP
sudo vim /etc/nginx/sites-available/ppt-helper

# 启用站点
sudo ln -s /etc/nginx/sites-available/ppt-helper /etc/nginx/sites-enabled/

# 删除默认站点（可选）
sudo rm /etc/nginx/sites-enabled/default

# 测试 Nginx 配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 步骤 7: 配置防火墙

```bash
# 如果使用 UFW
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
sudo ufw status

# 如果使用 iptables 或云服务器安全组
# 在云服务器控制台开放 80, 443 端口
```

### 步骤 8: 访问应用

打开浏览器访问:
```
http://192.168.1.100
```

---

## 🔧 常用管理命令

### 服务管理

```bash
# 查看服务状态
sudo systemctl status ppt-helper-backend
sudo systemctl status ppt-helper-frontend

# 重启服务
sudo systemctl restart ppt-helper-backend
sudo systemctl restart ppt-helper-frontend

# 停止服务
sudo systemctl stop ppt-helper-backend
sudo systemctl stop ppt-helper-frontend

# 查看日志
sudo journalctl -u ppt-helper-backend -f
sudo journalctl -u ppt-helper-frontend -f
```

### Nginx 管理

```bash
# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 更新代码

```bash
# 进入项目目录
cd /opt/ppt_helper

# 拉取最新代码
git pull

# 更新后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ppt-helper-backend

# 更新前端
cd ../frontend
npm install
npm run build
sudo systemctl restart ppt-helper-frontend
```

---

## 🔒 安全加固（可选但推荐）

### 1. 配置 HTTPS（需要域名）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取 SSL 证书
sudo certbot --nginx -d yourdomain.com

# 自动续期
sudo systemctl enable certbot.timer
```

### 2. 限制上传文件大小

已在 Nginx 配置中设置 `client_max_body_size 50M`

### 3. 配置进程监控

```bash
# 安装 supervisor（可选，代替 systemd）
sudo apt install -y supervisor

# 或使用 PM2（用于 Node.js）
sudo npm install -g pm2
```

---

## 🐛 故障排查

### 问题 1: 无法访问网站

```bash
# 检查服务是否运行
sudo systemctl status ppt-helper-backend
sudo systemctl status ppt-helper-frontend
sudo systemctl status nginx

# 检查端口占用
sudo netstat -tulnp | grep -E '3000|8000|80'

# 检查防火墙
sudo ufw status
```

### 问题 2: 后端 API 错误

```bash
# 查看后端日志
sudo journalctl -u ppt-helper-backend -n 100

# 检查环境变量
cat /opt/ppt_helper/backend/.env

# 手动测试后端
cd /opt/ppt_helper/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 问题 3: 前端无法连接后端

```bash
# 检查前端环境变量
cat /opt/ppt_helper/frontend/.env.local

# 确保 NEXT_PUBLIC_API_URL 正确
# 应该是: http://你的服务器IP:8000 或 http://yourdomain.com/api
```

### 问题 4: 文件上传失败

```bash
# 检查上传目录权限
ls -la /opt/ppt_helper/backend/uploads
sudo chown -R ubuntu:ubuntu /opt/ppt_helper/backend/uploads
sudo chmod -R 755 /opt/ppt_helper/backend/uploads
```

---

## 📊 性能优化

### 1. 启用 Gzip 压缩

在 Nginx 配置中添加:
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/javascript application/json;
```

### 2. 配置缓存

```nginx
# 静态文件缓存
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 7d;
    add_header Cache-Control "public, immutable";
}
```

### 3. 增加 Worker 数量

根据服务器 CPU 核心数调整 backend 服务的 workers:
```bash
# 在 /etc/systemd/system/ppt-helper-backend.service 中
ExecStart=/opt/ppt_helper/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🎯 一键部署脚本

我已为你准备了自动化部署脚本，见 `deploy.sh`。

使用方法:
```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

---

## 📞 需要帮助？

- 查看日志: `sudo journalctl -u ppt-helper-backend -f`
- 检查配置: `/opt/ppt_helper/backend/.env`
- API 文档: `http://你的IP:8000/docs`
