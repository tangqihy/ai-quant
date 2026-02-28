import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  StockOutlined,
  ExperimentOutlined,
  LineChartOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/stocks', icon: <StockOutlined />, label: '股票列表' },
    { key: '/backtest', icon: <ExperimentOutlined />, label: '回测配置' },
    { key: '/analysis', icon: <LineChartOutlined />, label: '收益分析' },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          background: 'linear-gradient(180deg, #001529 0%, #002140 100%)',
          boxShadow: '2px 0 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}>
          <LineChartOutlined style={{ color: '#1890ff', fontSize: 22 }} />
          <span style={{ color: '#fff', fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>
            AI 量化系统
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            marginTop: 8,
            borderRight: 'none',
          }}
        />
        <div style={{
          position: 'absolute',
          bottom: 16,
          left: 0,
          right: 0,
          textAlign: 'center',
          color: 'rgba(255,255,255,0.3)',
          fontSize: 11,
        }}>
          v1.0.0 · Powered by AkShare
        </div>
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          zIndex: 1,
        }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#262626' }}>
            A股量化交易回测系统
          </h2>
          <span style={{ color: '#8c8c8c', fontSize: 13 }}>
            Quantitative Trading System
          </span>
        </Header>
        <Content style={{
          margin: 16,
          padding: 24,
          background: '#f5f7fa',
          minHeight: 280,
          borderRadius: 8,
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
