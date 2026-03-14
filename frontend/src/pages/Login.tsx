import React, { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { LockOutlined, LineChartOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { loginApi } from '../services/api';
import { setToken } from '../services/auth';

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: { password: string }) => {
    setLoading(true);
    try {
      const res = await loginApi(values.password);
      if (res?.success && res?.token) {
        setToken(res.token);
        message.success('登录成功');
        navigate('/', { replace: true });
      } else {
        message.error('登录失败');
      }
    } catch (e: unknown) {
      const err = e as { response?: { status?: number }; message?: string };
      if (err?.response?.status === 401) {
        message.error('密码错误');
      } else {
        message.error(err?.message || '登录失败');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#000000',
        padding: 24,
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          borderRadius: 4,
          border: '1px solid rgba(0, 255, 65, 0.25)',
          boxShadow: '0 0 24px rgba(0, 255, 65, 0.15)',
          background: '#0a0a0a',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <LineChartOutlined style={{ fontSize: 48, color: '#00ff41', marginBottom: 12, textShadow: '0 0 12px rgba(0, 255, 65, 0.5)' }} />
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, color: '#00ff41' }}>AI 量化系统</h1>
          <p style={{ margin: '8px 0 0', color: 'rgba(0, 255, 65, 0.6)', fontSize: 14 }}>请输入访问密码</p>
        </div>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
          layout="vertical"
        >
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoFocus
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login;
