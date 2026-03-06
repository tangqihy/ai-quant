import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AnimatePresence } from 'framer-motion';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import StockList from './pages/StockList';
import BacktestConfig from './pages/BacktestConfig';
import Analysis from './pages/Analysis';
import WatchlistManager from './pages/WatchlistManager';
import StockDetail from './pages/StockDetail';
import { PageTransition } from './components/common/PageTransition';
import { useTheme } from './hooks/useTheme';

// 路由配置
const AppRoutes: React.FC = () => {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
        <Route path="/stocks" element={<PageTransition><StockList /></PageTransition>} />
        <Route path="/stocks/:symbol" element={<PageTransition><StockDetail /></PageTransition>} />
        <Route path="/watchlist" element={<PageTransition><WatchlistManager /></PageTransition>} />
        <Route path="/backtest" element={<PageTransition><BacktestConfig /></PageTransition>} />
        <Route path="/analysis" element={<PageTransition><Analysis /></PageTransition>} />
      </Routes>
    </AnimatePresence>
  );
};

function App() {
  const { antdConfig, isDark, toggleTheme } = useTheme();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        ...antdConfig,
      }}
    >
      <BrowserRouter basename="/quant">
        <MainLayout isDark={isDark} onThemeToggle={toggleTheme}>
          <AppRoutes />
        </MainLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
