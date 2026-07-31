import React, { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { LockOutlined, EditOutlined } from '@ant-design/icons';
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
        background: 'var(--paper)',
        padding: 24,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 400,
          background: 'var(--paper-card)',
          border: '1.5px solid var(--line-strong)',
          borderRadius: 'var(--sketch-radius)',
          boxShadow: '4px 6px 0 rgba(45, 42, 38, 0.1)',
          padding: '36px 32px 28px',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <EditOutlined style={{ fontSize: 36, color: 'var(--accent)', marginBottom: 8 }} />
          <h1
            className="hand-font"
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 400,
              color: 'var(--ink)',
              textDecoration: 'underline wavy var(--accent-warm) 2px',
              textUnderlineOffset: 8,
            }}
          >
            AI 量化手账
          </h1>
          <p
            style={{
              margin: '12px 0 0',
              color: 'var(--ink-soft)',
              fontSize: 13,
              fontFamily: 'var(--mono-font)',
            }}
          >
            记录你的每一笔研究
          </p>
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
              placeholder="访问密码"
              autoFocus
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              翻开手账
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default Login;
