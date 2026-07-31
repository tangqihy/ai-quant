import React, { useState } from 'react';
import { Layout, Menu, Drawer, Button } from 'antd';
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
  FundOutlined,
  MenuOutlined,
  RadarChartOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { SearchBar } from '../components/SearchBar';
import { VersionDisplay } from '../components/common/VersionDisplay';
import { GlitchText } from '../components/common/GlitchText';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
  isDark?: boolean;
  onThemeToggle?: () => void;
}

const SIDER_BG = '#02040a';
const HEADER_BG = '#050815';
const CONTENT_BG = '#02040a';
const NEON_CYAN = '#00f0ff';
const NEON_BORDER = 'rgba(0, 240, 255, 0.32)';

const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  isDark = true,
  onThemeToggle,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const menuItems = [
    { key: '/', icon: <StarFilled />, label: '自选' },
    { key: '/watchlist', icon: <FolderOutlined />, label: '分组管理' },
    { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
    { key: '/analysis', icon: <LineChartOutlined />, label: '分析' },
    { key: '/factors', icon: <FundOutlined />, label: '因子分析' },
    { key: '/signals', icon: <RadarChartOutlined />, label: '信号监控' },
    { key: '/stock-canvas', icon: <AppstoreOutlined />, label: '研究画布' },
    { key: '/simulation', icon: <DollarOutlined />, label: '模拟交易' },
    { key: '/risk', icon: <SafetyOutlined />, label: '风控管理' },
    { key: '/strategy-template', icon: <BookOutlined />, label: '策略模板' },
  ];

  const selectedKey = (() => {
    if (location.pathname === '/') return '/';
    // 子路径归并到父菜单，如 /stock-canvas/01810.HK → /stock-canvas
    const match = menuItems.find((m) => m.key !== '/' && location.pathname.startsWith(m.key + '/'));
    return match ? match.key : location.pathname;
  })();

  const go = (key: string) => {
    navigate(key);
    setDrawerOpen(false);
  };

  return (
    <Layout style={{ minHeight: '100vh', background: CONTENT_BG }}>
      <Sider
        width={200}
        breakpoint="lg"
        collapsedWidth="0"
        trigger={null}
        style={{
          background: SIDER_BG,
          borderRight: `1px solid ${NEON_BORDER}`,
          boxShadow: '0 0 18px rgba(0, 240, 255, 0.18)',
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
          <LineChartOutlined style={{ color: NEON_CYAN, fontSize: 20 }} />
          <GlitchText
            text="AI-QUANT"
            className=""
          />
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
            color: 'rgba(0, 240, 255, 0.45)',
            fontSize: 11,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          Powered by Tushare
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
          <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, gap: 8 }}>
            <Button
              className="futu-menu-toggle"
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              style={{ color: NEON_CYAN, fontSize: 18 }}
            />
            <SearchBar />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                color: 'rgba(0, 240, 255, 0.65)',
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
      {/* 移动端侧边菜单 Drawer */}
      <Drawer
        placement="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        closable={false}
        size={220}
        styles={{
          body: {
            padding: 0,
            background: SIDER_BG,
          },
          header: { display: 'none' },
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
            color: NEON_CYAN,
          }}
        >
          <LineChartOutlined style={{ fontSize: 20 }} />
          <GlitchText text="AI-QUANT" className="" />
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => go(key)}
          style={{ background: 'transparent', borderRight: 'none' }}
        />
      </Drawer>
      <nav
        className="futu-bottom-nav"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 48,
          background: '#050815',
          borderTop: `1px solid ${NEON_BORDER}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 32,
          zIndex: 100,
          boxShadow: '0 -0 14px rgba(0, 240, 255, 0.22)',
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/')}
          style={{
            background: 'none',
            border: 'none',
            color: location.pathname === '/' ? NEON_CYAN : 'rgba(0, 240, 255, 0.55)',
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
            color: location.pathname === '/backtest' ? NEON_CYAN : 'rgba(0, 240, 255, 0.55)',
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
            color: location.pathname === '/analysis' ? NEON_CYAN : 'rgba(0, 240, 255, 0.55)',
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
