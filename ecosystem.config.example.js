// PM2 配置文件模板
// 复制此文件为 ecosystem.config.js 并修改路径

module.exports = {
  apps: [
    {
      name: 'ppt-backend',
      cwd: '/path/to/ppt_helper/backend',  // 修改为你的后端路径
      script: '/path/to/miniconda3/envs/ppt_helper/bin/uvicorn',  // 修改为你的 uvicorn 路径
      args: 'app.main:app --host 127.0.0.1 --port 8000',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 5000
    },
    {
      name: 'ppt-frontend',
      cwd: '/path/to/ppt_helper/frontend',  // 修改为你的前端路径
      script: 'npm',
      args: 'run dev',
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 5000
    }
  ]
};

// 使用方法:
// 1. 复制: cp ecosystem.config.example.js ecosystem.config.js
// 2. 修改路径
// 3. 启动: pm2 start ecosystem.config.js
// 4. 保存: pm2 save
// 5. 开机自启: pm2 startup
