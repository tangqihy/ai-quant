import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  StockOutlined,
  ExperimentOutlined,
  LineChartOutlined,
  StarFilled,
} from '@ant-design/icons';
import { ThemeToggle } from '../components/common/ThemeToggle';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
  isDark?: boolean;
  onThemeToggle?: () => void;
}

const MainLayout: React.FC<MainLayoutProps> = ({ 
  children, 
  isDark = false, 
  onThemeToggle 
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/stocks', icon: <StockOutlined />, label: '股票列表' },
    { key: '/watchlist', icon: <StarFilled />, label: '我的自选' },
    { key: '/backtest', icon: <ExperimentOutlined />, label: '回测配置' },
    { key: '/analysis', icon: <LineChartOutlined />, label: '收益分析' },
  ];

  // 暗色模式样式
  const siderBg = isDark 
    ? 'linear-gradient(180deg, #000000 0%, #141414 100%)'
    : 'linear-gradient(180deg, #001529 0%, #002140 100%)';
  
  const headerBg = isDark ? '#1f1f1f' : '#ffffff';
  const contentBg = isDark ? '#000000' : '#f5f7fa';
  const textColor = isDark ? '#ffffff' : '#262626';
  const secondaryTextColor = isDark ? '#a6a6a6' : '#8c8c8c';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          background: siderBg,
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
          background: headerBg,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          zIndex: 1,
        }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: textColor }}>
            A股量化交易回测系统
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ color: secondaryTextColor, fontSize: 13 }}>
              Quantitative Trading System
            </span>
            {onThemeToggle && (
              <ThemeToggle isDark={isDark} onToggle={onThemeToggle} />
            )}
          </div>
        </Header>
        <Content style={{
          margin: 16,
          padding: 24,
          background: contentBg,
          minHeight: 280,
          borderRadius: 8,
          transition: 'background-color 0.3s ease',
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
