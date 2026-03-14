import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  StarFilled,
  FolderOutlined,
  ExperimentOutlined,
  LineChartOutlined,
  DollarOutlined,
  SafetyOutlined,
  UserOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { SearchBar } from '../components/SearchBar';
import { VersionDisplay } from '../components/common/VersionDisplay';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
  isDark?: boolean;
  onThemeToggle?: () => void;
}

const SIDER_BG = '#000000';
const HEADER_BG = '#0a0a0a';
const CONTENT_BG = '#000000';
const NEON_GREEN = '#00ff41';
const NEON_BORDER = 'rgba(0, 255, 65, 0.25)';

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
    { key: '/simulation', icon: <DollarOutlined />, label: '模拟交易' },
    { key: '/risk', icon: <SafetyOutlined />, label: '风控管理' },
    { key: '/strategy-template', icon: <BookOutlined />, label: '策略模板' },
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
          borderRight: `1px solid ${NEON_BORDER}`,
          boxShadow: '0 0 12px rgba(0, 255, 65, 0.08)',
        }}
      >
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            borderBottom: `1px solid ${NEON_BORDER}`,
          }}
        >
          <LineChartOutlined style={{ color: NEON_GREEN, fontSize: 20 }} />
          <span
            style={{
              color: NEON_GREEN,
              fontSize: 15,
              fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace",
              textShadow: '0 0 8px rgba(0, 255, 65, 0.5)',
            }}
          >
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
            color: 'rgba(0, 255, 65, 0.35)',
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          Powered by AkShare
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: HEADER_BG,
            padding: '0 12px 0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            borderBottom: `1px solid ${NEON_BORDER}`,
            height: 56,
            minHeight: 56,
            boxShadow: '0 0 12px rgba(0, 255, 65, 0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
            <SearchBar />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                color: 'rgba(0, 255, 65, 0.55)',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontFamily: "'JetBrains Mono', monospace",
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
          className="futu-content-with-bottom-nav"
          style={{
            margin: 0,
            padding: '16px 12px 64px',
            background: CONTENT_BG,
            minHeight: 'calc(100vh - 56px)',
            overflow: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
      <nav
        className="futu-bottom-nav"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 48,
          background: '#0a0a0a',
          borderTop: `1px solid ${NEON_BORDER}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 32,
          zIndex: 100,
          boxShadow: '0 -0 12px rgba(0, 255, 65, 0.05)',
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/')}
          style={{
            background: 'none',
            border: 'none',
            color: location.pathname === '/' ? NEON_GREEN : 'rgba(0, 255, 65, 0.55)',
            fontSize: 13,
            fontWeight: location.pathname === '/' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: "'JetBrains Mono', monospace",
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
            color: location.pathname === '/backtest' ? NEON_GREEN : 'rgba(0, 255, 65, 0.55)',
            fontSize: 13,
            fontWeight: location.pathname === '/backtest' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: "'JetBrains Mono', monospace",
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
            color: location.pathname === '/analysis' ? NEON_GREEN : 'rgba(0, 255, 65, 0.55)',
            fontSize: 13,
            fontWeight: location.pathname === '/analysis' ? 600 : 400,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          <LineChartOutlined /> 分析
        </button>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          <VersionDisplay />
        </div>
      </nav>
    </Layout>
  );
};

export default MainLayout;
