#!/bin/bash
# PPT Helper 启动脚本 (Linux/Mac)

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动 PPT Helper${NC}"
echo -e "${GREEN}========================================${NC}\n"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 启动后端
echo -e "${YELLOW}启动后端服务...${NC}"
cd "$SCRIPT_DIR/backend"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
    python3.11 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}请先创建 .env 文件并配置 GOOGLE_API_KEY${NC}"
    exit 1
fi

# 后台启动后端
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ 后端已启动 (PID: $BACKEND_PID)${NC}"
echo $BACKEND_PID > ../backend.pid

# 启动前端
echo -e "${YELLOW}启动前端服务...${NC}"
cd "$SCRIPT_DIR/frontend"

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}安装前端依赖...${NC}"
    npm install
fi

# 后台启动前端
nohup npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}✓ 前端已启动 (PID: $FRONTEND_PID)${NC}"
echo $FRONTEND_PID > ../frontend.pid

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  服务已启动!${NC}"
echo -e "${GREEN}========================================${NC}\n"
echo -e "访问地址: ${GREEN}http://localhost:3000${NC}"
echo -e "后端 API: ${GREEN}http://localhost:8000${NC}"
echo -e "API 文档: ${GREEN}http://localhost:8000/docs${NC}\n"
echo -e "查看日志:"
echo -e "  后端: ${YELLOW}tail -f backend.log${NC}"
echo -e "  前端: ${YELLOW}tail -f frontend.log${NC}\n"
echo -e "停止服务:"
echo -e "  ${YELLOW}./stop.sh${NC}\n"
