# 快速部署检查清单

## 部署前准备
- [ ] 有一台 Linux 服务器（Ubuntu 20.04+ 推荐）
- [ ] 知道服务器的 IP 地址
- [ ] 有 SSH 访问权限
- [ ] 有 Google Gemini API Key

## 部署步骤（推荐使用自动化脚本）

### 方式 1: 一键自动部署（最简单）

1. **上传项目到服务器**
```bash
# 在本地运行
scp -r /path/to/ppt_helper user@your-server-ip:/opt/
```

2. **运行部署脚本**
```bash
# 在服务器上运行
cd /opt/ppt_helper
chmod +x deploy.sh
sudo ./deploy.sh
```

3. **按提示输入**
   - 服务器 IP 地址
   - Gemini API Key
   - 安装路径（直接回车使用默认）

4. **访问应用**
   - 浏览器打开: `http://你的服务器IP`

### 方式 2: 手动部署（详细步骤）

参考 `deploy.md` 文件中的详细步骤。

## 部署后检查

```bash
# 检查服务状态
sudo systemctl status ppt-helper-backend
sudo systemctl status ppt-helper-frontend
sudo systemctl status nginx

# 查看日志
sudo journalctl -u ppt-helper-backend -f
sudo journalctl -u ppt-helper-frontend -f

# 测试访问
curl http://localhost:8000/api/health
curl http://localhost:3000
```

## 常见问题

### 无法访问？
1. 检查云服务器安全组是否开放 80 端口
2. 检查防火墙: `sudo ufw status`
3. 检查 Nginx: `sudo nginx -t && sudo systemctl restart nginx`

### 文件上传失败？
```bash
# 检查权限
sudo chown -R your-user:your-user /opt/ppt_helper/backend/uploads
sudo chmod -R 755 /opt/ppt_helper/backend/uploads
```

### API 连接错误？
检查 `/opt/ppt_helper/frontend/.env.local` 中的 `NEXT_PUBLIC_API_URL` 是否正确

## 文件说明

- `deploy.md` - 详细的手动部署文档
- `deploy.sh` - 自动化部署脚本（Ubuntu/Debian）
- `start_all.sh` - 开发环境启动脚本
- `stop.sh` - 开发环境停止脚本

## 端口说明

- 80: Nginx (对外访问)
- 3000: Next.js 前端（内网）
- 8000: FastAPI 后端（内网）

生产环境通过 Nginx 反向代理，只需开放 80 端口。
