import React, { useState, useEffect } from 'react';
import { Card, Tabs, Typography, Button, message, Alert, Space, Tag, Divider } from 'antd';
import { CopyOutlined, PlayCircleOutlined, BookOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

// 策略模板代码
const STRATEGY_TEMPLATES = {
  ma_cross: `import pandas as pd
import numpy as np
from typing import Dict, Any
from app.strategies.base import BaseStrategy

class MACrossStrategy(BaseStrategy):
    """
    均线交叉策略 - 基础模板
    
    策略逻辑：
    - 当短期均线上穿长期均线时买入（金叉）
    - 当短期均线下穿长期均线时卖出（死叉）
    
    可调整参数：
    - short_window: 短期均线周期（默认5）
    - long_window: 长期均线周期（默认20）
    """
    
    strategy_id = "ma_cross"
    name = "均线交叉策略"
    description = "基于短期和长期均线交叉产生买卖信号"
    
    param_schema = [
        {"name": "short_window", "type": "int", "default": 5, "min": 1, "max": 100, "description": "短期均线周期"},
        {"name": "long_window", "type": "int", "default": 20, "min": 1, "max": 200, "description": "长期均线周期"},
    ]
    
    def generate_signals(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """
        生成买卖信号
        
        返回的DataFrame需要包含：
        - buy_signal: bool, 买入信号
        - sell_signal: bool, 卖出信号
        """
        short_window = params.get("short_window", 5)
        long_window = params.get("long_window", 20)
        
        # 计算均线
        df["ma_short"] = df["close"].rolling(window=short_window).mean()
        df["ma_long"] = df["close"].rolling(window=long_window).mean()
        
        # 生成信号
        df["buy_signal"] = (df["ma_short"] > df["ma_long"]) & (
            df["ma_short"].shift(1) <= df["ma_long"].shift(1)
        )
        df["sell_signal"] = (df["ma_short"] < df["ma_long"]) & (
            df["ma_short"].shift(1) >= df["ma_long"].shift(1)
        )
        
        return df
`,

  rsi: `import pandas as pd
import numpy as np
from typing import Dict, Any
from app.strategies.base import BaseStrategy

class RSIStrategy(BaseStrategy):
    """
    RSI策略 - 基础模板
    
    策略逻辑：
    - RSI < oversold（超卖线）时买入
    - RSI > overbought（超买线）时卖出
    
    可调整参数：
    - period: RSI计算周期（默认14）
    - oversold: 超卖阈值（默认30）
    - overbought: 超买阈值（默认70）
    """
    
    strategy_id = "rsi"
    name = "RSI策略"
    description = "基于RSI指标的超买超卖策略"
    
    param_schema = [
        {"name": "period", "type": "int", "default": 14, "min": 1, "max": 100, "description": "RSI周期"},
        {"name": "oversold", "type": "int", "default": 30, "min": 1, "max": 50, "description": "超卖阈值"},
        {"name": "overbought", "type": "int", "default": 70, "min": 50, "max": 99, "description": "超买阈值"},
    ]
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """生成买卖信号"""
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        
        # 计算RSI
        df["rsi"] = self.calculate_rsi(df["close"], period)
        
        # 生成信号
        df["buy_signal"] = df["rsi"] < oversold
        df["sell_signal"] = df["rsi"] > overbought
        
        return df
`,

  custom: `# 自定义策略模板
import pandas as pd
import numpy as np
from typing import Dict, Any
from app.strategies.base import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    """
    我的自定义策略
    
    在这里描述你的策略逻辑...
    """
    
    strategy_id = "my_custom"  # 唯一标识符
    name = "我的自定义策略"
    description = "在这里描述你的策略"
    
    # 定义可调参数
    param_schema = [
        {"name": "param1", "type": "int", "default": 10, "min": 1, "max": 100, "description": "参数1说明"},
        {"name": "param2", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "description": "参数2说明"},
    ]
    
    def generate_signals(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """
        生成买卖信号
        
        必须返回包含以下列的DataFrame：
        - buy_signal: bool, 买入信号
        - sell_signal: bool, 卖出信号
        
        可以添加其他指标列用于可视化
        """
        param1 = params.get("param1", 10)
        param2 = params.get("param2", 0.5)
        
        # 在这里实现你的策略逻辑
        # 示例：简单的价格突破策略
        df["ma"] = df["close"].rolling(window=param1).mean()
        df["std"] = df["close"].rolling(window=param1).std()
        df["upper"] = df["ma"] + df["std"] * param2
        df["lower"] = df["ma"] - df["std"] * param2
        
        # 买入信号：价格突破上轨
        df["buy_signal"] = df["close"] > df["upper"]
        # 卖出信号：价格跌破下轨
        df["sell_signal"] = df["close"] < df["lower"]
        
        return df
`
};

const StrategyTemplate: React.FC = () => {
  const [activeTab, setActiveTab] = useState('ma_cross');

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    message.success('代码已复制到剪贴板');
  };

  const codeBlockStyle = {
    background: '#0a0a0a',
    color: 'rgba(0, 255, 65, 0.9)',
    padding: 16,
    borderRadius: 4,
    overflow: 'auto' as const,
    fontSize: 13,
    lineHeight: 1.5,
    border: '1px solid rgba(0, 255, 65, 0.25)',
  };

  const items = [
    {
      key: 'ma_cross',
      label: '均线交叉策略',
      children: (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              message="策略说明"
              description="基于短期和长期均线交叉产生买卖信号。当短期均线上穿长期均线时买入（金叉），下穿时卖出（死叉）。"
              type="info"
              showIcon
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <Tag color="blue">short_window: 短期均线周期</Tag>
                <Tag color="blue">long_window: 长期均线周期</Tag>
              </Space>
              <Button icon={<CopyOutlined />} onClick={() => handleCopy(STRATEGY_TEMPLATES.ma_cross)}>
                复制代码
              </Button>
            </div>
            <pre style={codeBlockStyle}>
              <code style={{ color: 'rgba(0, 255, 65, 0.9)' }}>{STRATEGY_TEMPLATES.ma_cross}</code>
            </pre>
          </Space>
        </Card>
      ),
    },
    {
      key: 'rsi',
      label: 'RSI策略',
      children: (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              message="策略说明"
              description="基于RSI指标的超买超卖策略。RSI低于超卖阈值时买入，高于超买阈值时卖出。"
              type="info"
              showIcon
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <Tag color="blue">period: RSI计算周期</Tag>
                <Tag color="blue">oversold: 超卖阈值</Tag>
                <Tag color="blue">overbought: 超买阈值</Tag>
              </Space>
              <Button icon={<CopyOutlined />} onClick={() => handleCopy(STRATEGY_TEMPLATES.rsi)}>
                复制代码
              </Button>
            </div>
            <pre style={codeBlockStyle}>
              <code style={{ color: 'rgba(0, 255, 65, 0.9)' }}>{STRATEGY_TEMPLATES.rsi}</code>
            </pre>
          </Space>
        </Card>
      ),
    },
    {
      key: 'custom',
      label: '自定义策略模板',
      children: (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              message="开发指南"
              description="复制此模板，修改策略ID、名称和generate_signals方法，实现你自己的策略逻辑。"
              type="warning"
              showIcon
            />
            <Alert
              message="安全提醒"
              description="自定义策略代码保存在本地，不会上传到Git仓库，请妥善保管你的Alpha策略。"
              type="error"
              showIcon
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button icon={<CopyOutlined />} onClick={() => handleCopy(STRATEGY_TEMPLATES.custom)}>
                复制模板
              </Button>
            </div>
            <pre style={codeBlockStyle}>
              <code style={{ color: 'rgba(0, 255, 65, 0.9)' }}>{STRATEGY_TEMPLATES.custom}</code>
            </pre>
          </Space>
        </Card>
      ),
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <Title level={2} style={{ color: '#00ff41' }}>
        <BookOutlined /> 策略开发模板
      </Title>
      
      <Paragraph style={{ color: 'rgba(0, 255, 65, 0.7)' }}>
        以下是内置策略的完整代码模板，你可以复制并修改来开发自己的策略。
        所有策略都继承自 BaseStrategy 基类，只需实现 generate_signals 方法即可。
      </Paragraph>

      <Divider />

      <Card>
        <Title level={4}>策略开发步骤</Title>
        <ol style={{ lineHeight: 2 }}>
          <li>复制下方的策略模板代码</li>
          <li>修改 <code>strategy_id</code>（唯一标识符）和 <code>name</code>（显示名称）</li>
          <li>在 <code>param_schema</code> 中定义可调参数</li>
          <li>在 <code>generate_signals</code> 中实现买卖信号逻辑</li>
          <li>将代码保存到 <code>app/strategies/</code> 目录下</li>
          <li>在 <code>app/strategies/__init__.py</code> 中注册你的策略</li>
          <li>重启后端服务即可使用</li>
        </ol>
      </Card>

      <Divider />

      <Tabs 
        activeKey={activeTab} 
        onChange={setActiveTab}
        items={items}
        style={{ marginTop: 24 }}
      />
    </div>
  );
};

export default StrategyTemplate;
