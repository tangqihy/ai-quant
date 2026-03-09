module.exports = {
  apps: [{
    name: 'quant-backend',
    script: './start.sh',
    interpreter: 'bash',
    cwd: '/root/.openclaw/workspace/ai-quant',
    env: {
      PYTHONPATH: '/root/.openclaw/workspace/ai-quant',
      QUANT_AUTH_PASSWORD: 'tangqi2024',
      JQ_USERNAME: '17682443337',
      JQ_PASSWORD: 'Yvhkyjj11385171'
    },
    watch: false,
    autorestart: true
  }]
}
