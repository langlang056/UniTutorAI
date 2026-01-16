# UniTutor AI - 智能课件讲解助手
在线使用网址(需自备gemini apikey)：https://unitutorai.com/

基于 Gemini Vision 的 PDF 课件智能解析系统，将复杂的学术内容转化为通俗易懂的中文解释。

## 功能特点

- 使用 PyMuPDF 将 PDF 转为高清图像，通过 Gemini Vision 分析
- AI 自动识别 PPT 中的文字、图表、公式，生成中文讲解
- 左侧原始 PDF，右侧 AI 解释，实时同步
- 支持 LaTeX 公式渲染
- AI 追问助手，可针对当前页面内容进行追问

## 环境要求

- Python 3.11+
- Node.js 18+
- Google Gemini API Key (https://aistudio.google.com/apikey)

## 本地开发

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 GOOGLE_API_KEY

uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 服务器部署

以下以 Ubuntu + Miniconda + Nginx + PM2 为例。

### 1. 安装 Miniconda

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p $HOME/miniconda3
$HOME/miniconda3/bin/conda init bash
source ~/.bashrc
```

### 2. 安装 Node.js

```bash
cd /tmp
curl -fsSL https://nodejs.org/dist/v20.11.0/node-v20.11.0-linux-x64.tar.xz -o node.tar.xz
tar -xf node.tar.xz
sudo cp -r node-v20.11.0-linux-x64/{bin,lib,share} /usr/local/
```

### 3. 配置后端

```bash
conda create -n ppt_helper python=3.11 -y
conda activate ppt_helper

cd /path/to/ppt_helper/backend
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 GOOGLE_API_KEY
```

### 4. 配置前端

```bash
cd /path/to/ppt_helper/frontend
npm install

# 如果使用 Nginx 反向代理，创建 .env.local
echo "NEXT_PUBLIC_API_URL=/api" > .env.local
```

### 5. 配置 Nginx

安装 Nginx：

```bash
sudo apt install -y nginx
```

创建配置文件 `/etc/nginx/sites-available/ppt-helper`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    client_max_body_size 100M;
}
```

启用配置：

```bash
sudo ln -sf /etc/nginx/sites-available/ppt-helper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 6. 使用 PM2 管理进程

安装 PM2：

```bash
npm install -g pm2
```

创建配置文件 `ecosystem.config.js`（参考 `ecosystem.config.example.js`）：

```javascript
module.exports = {
  apps: [
    {
      name: 'ppt-backend',
      cwd: '/path/to/ppt_helper/backend',
      script: '/path/to/miniconda3/envs/ppt_helper/bin/uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8000',
      interpreter: 'none',
      autorestart: true
    },
    {
      name: 'ppt-frontend',
      cwd: '/path/to/ppt_helper/frontend',
      script: 'npm',
      args: 'run dev',
      autorestart: true
    }
  ]
};
```

启动服务：

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # 配置开机自启
```

### 7. 防火墙配置

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### PM2 常用命令

| 命令 | 说明 |
|------|------|
| `pm2 status` | 查看服务状态 |
| `pm2 logs` | 查看日志 |
| `pm2 restart all` | 重启所有服务 |
| `pm2 stop all` | 停止所有服务 |

## 技术栈

**后端**: FastAPI, PyMuPDF, Google Gemini API, SQLite

**前端**: Next.js 14, react-pdf, Zustand, Tailwind CSS

## 项目结构

```
ppt_helper/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 主路由
│   │   ├── config.py         # 配置管理
│   │   ├── models/           # 数据库模型
│   │   └── services/         # PDF解析、LLM服务
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/                  # Next.js 页面
│   ├── components/           # React 组件
│   ├── store/                # Zustand 状态管理
│   ├── lib/                  # API 调用
│   └── package.json
├── ecosystem.config.example.js  # PM2 配置模板
└── README.md
```

## 许可

仅供个人学习使用。
