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
  EditOutlined,
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

/** 手绘风 Logo：手写字 + 波浪下划线 */
const BrandLogo: React.FC = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    <EditOutlined style={{ color: 'var(--accent)', fontSize: 18 }} />
    <span
      className="hand-font"
      style={{
        fontSize: 24,
        color: 'var(--ink)',
        lineHeight: 1,
        textDecoration: 'underline wavy var(--accent-warm) 2px',
        textUnderlineOffset: 6,
      }}
    >
      AI 量化手账
    </span>
  </div>
);

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
    <Layout style={{ minHeight: '100vh', background: 'var(--paper)' }}>
      <Sider
        width={200}
        breakpoint="lg"
        collapsedWidth="0"
        trigger={null}
        style={{
          background: 'var(--paper-elevated)',
          borderRight: '1.5px solid var(--line)',
        }}
      >
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1.5px dashed var(--line)',
          }}
        >
          <BrandLogo />
        </div>
        <Menu
          theme="light"
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
            color: 'var(--ink-faint)',
            fontSize: 11,
            fontFamily: 'var(--mono-font)',
          }}
        >
          Powered by Tushare
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: 'var(--paper-elevated)',
            padding: '0 12px 0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            borderBottom: '1.5px solid var(--line)',
            height: 56,
            minHeight: 56,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, gap: 8 }}>
            <Button
              className="futu-menu-toggle"
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              style={{ color: 'var(--ink)', fontSize: 18 }}
            />
            <SearchBar />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                color: 'var(--ink-soft)',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontFamily: 'var(--mono-font)',
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
            background: 'var(--paper)',
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
            background: 'var(--paper-elevated)',
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
            borderBottom: '1.5px dashed var(--line)',
          }}
        >
          <BrandLogo />
        </div>
        <Menu
          theme="light"
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
          background: 'var(--paper-elevated)',
          borderTop: '1.5px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 32,
          zIndex: 100,
        }}
      >
        {[
          { key: '/', icon: <StarFilled />, label: '自选' },
          { key: '/backtest', icon: <ExperimentOutlined />, label: '回测' },
          { key: '/analysis', icon: <LineChartOutlined />, label: '分析' },
        ].map((item) => {
          const active = location.pathname === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => navigate(item.key)}
              style={{
                background: active ? 'var(--marker)' : 'none',
                border: 'none',
                borderRadius: 'var(--sketch-radius-sm)',
                padding: '4px 10px',
                color: active ? 'var(--ink)' : 'var(--ink-faint)',
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {item.icon} {item.label}
            </button>
          );
        })}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          <VersionDisplay />
        </div>
      </nav>
    </Layout>
  );
};

export default MainLayout;
