module.exports = {
  apps: [{
    name: 'quant-backend',
    script: './start.sh',
    interpreter: 'bash',
    cwd: process.env.QUANT_APP_ROOT || __dirname,
    env: {
      PYTHONPATH: process.env.QUANT_APP_ROOT || __dirname,
      QUANT_AUTH_PASSWORD: process.env.QUANT_AUTH_PASSWORD,
      TUSHARE_TOKEN: process.env.TUSHARE_TOKEN
    },
    watch: false,
    autorestart: true
  }]
}
