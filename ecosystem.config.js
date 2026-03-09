// 使用 start.sh 启动，脚本内会设置 PYTHONPATH 并执行 uvicorn，确保 app 模块可被正确导入。
// 备选：若希望不用 bash，可改为 script: 'python', args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000']，并依赖下方 env.PYTHONPATH。
module.exports = {
  apps: [{
    name: 'quant-backend',
    script: 'start.sh',
    interpreter: 'bash',
    cwd: '/root/.openclaw/workspace/ai-quant',
    watch: false,
    autorestart: true,
    env: {
      PYTHONPATH: '/root/.openclaw/workspace/ai-quant'
    }
  }]
}
