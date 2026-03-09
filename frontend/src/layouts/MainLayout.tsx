import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  StarFilled,
  FolderOutlined,
  ExperimentOutlined,
  LineChartOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { SearchBar } from '../components/SearchBar';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
  isDark?: boolean;
  onThemeToggle?: () => void;
}

// 富途牛牛风格：深色专业交易
const SIDER_BG = '#0d0d0d';
const HEADER_BG = '#141414';
const CONTENT_BG = '#0a0a0a';
const MENU_SELECTED = '#1890ff';

const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  isDark = true,
  onThemeToggle,
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <StarFilled />, label: '自选' },
    { key: '/watchlist', icon: <FolderOutlined />, label: '分组管理' },
    { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
    { key: '/analysis', icon: <LineChartOutlined />, label: '分析' },
  ];

  const selectedKey = location.pathname === '/' ? '/' : location.pathname;

  return (
    <Layout style={{ minHeight: '100vh', background: CONTENT_BG }}>
      <Sider
        width={200}
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          background: SIDER_BG,
          borderRight: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <LineChartOutlined style={{ color: MENU_SELECTED, fontSize: 20 }} />
          <span style={{ color: '#fff', fontSize: 15, fontWeight: 600 }}>
            AI 量化
          </span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            marginTop: 8,
            borderRight: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 16,
            left: 0,
            right: 0,
            textAlign: 'center',
            color: 'rgba(255,255,255,0.25)',
            fontSize: 11,
          }}
        >
          Powered by AkShare
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: HEADER_BG,
            padding: '0 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            height: 56,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <SearchBar />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                color: 'rgba(255,255,255,0.5)',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <UserOutlined />
              用户
            </span>
            {onThemeToggle && (
              <ThemeToggle isDark={isDark} onToggle={onThemeToggle} />
            )}
          </div>
        </Header>
        <Content
          style={{
            margin: 0,
            padding: '16px 16px 60px',
            background: CONTENT_BG,
            minHeight: 'calc(100vh - 56px)',
            overflow: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
      {/* 底部导航栏：自选、回测、分析 */}
      <nav
        className="futu-bottom-nav"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 48,
          background: '#141414',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 32,
          zIndex: 100,
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/')}
          style={{
            background: 'none',
            border: 'none',
            color: location.pathname === '/' ? MENU_SELECTED : 'rgba(255,255,255,0.65)',
            fontSize: 13,
            fontWeight: location.pathname === '/' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <StarFilled /> 自选
        </button>
        <button
          type="button"
          onClick={() => navigate('/backtest')}
          style={{
            background: 'none',
            border: 'none',
            color: location.pathname === '/backtest' ? MENU_SELECTED : 'rgba(255,255,255,0.65)',
            fontSize: 13,
            fontWeight: location.pathname === '/backtest' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <ExperimentOutlined /> 回测
        </button>
        <button
          type="button"
          onClick={() => navigate('/analysis')}
          style={{
            background: 'none',
            border: 'none',
            color: location.pathname === '/analysis' ? MENU_SELECTED : 'rgba(255,255,255,0.65)',
            fontSize: 13,
            fontWeight: location.pathname === '/analysis' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <LineChartOutlined /> 分析
        </button>
      </nav>
    </Layout>
  );
};

export default MainLayout;
