import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AnimatePresence } from 'framer-motion';
import { WatchlistProvider } from './contexts/WatchlistContext';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import BacktestConfig from './pages/BacktestConfig';
import Analysis from './pages/Analysis';
import WatchlistManager from './pages/WatchlistManager';
import StockDetail from './pages/StockDetail';
import SimulationTrading from './pages/SimulationTrading';
import RiskManagement from './pages/RiskManagement';
import StrategyTemplate from './pages/StrategyTemplate';
import Login from './pages/Login';
import { PageTransition } from './components/common/PageTransition';
import { useTheme } from './hooks/useTheme';
import { getToken } from './services/auth';

const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!getToken()) return <Login />;
  return <>{children}</>;
};

// 路由配置
const AppRoutes: React.FC<{ isDark: boolean; onThemeToggle: () => void }> = ({ isDark, onThemeToggle }) => {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <MainLayout isDark={isDark} onThemeToggle={onThemeToggle}>
                <Routes location={location} key={`in-${location.pathname}`}>
                  <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
                  <Route path="/stocks/:symbol" element={<PageTransition><StockDetail /></PageTransition>} />
                  <Route path="/watchlist" element={<PageTransition><WatchlistManager /></PageTransition>} />
                  <Route path="/backtest" element={<PageTransition><BacktestConfig /></PageTransition>} />
                  <Route path="/analysis" element={<PageTransition><Analysis /></PageTransition>} />
                  <Route path="/simulation" element={<PageTransition><SimulationTrading /></PageTransition>} />
                  <Route path="/risk" element={<PageTransition><RiskManagement /></PageTransition>} />
                  <Route path="/strategy-template" element={<PageTransition><StrategyTemplate /></PageTransition>} />
                </Routes>
              </MainLayout>
            </RequireAuth>
          }
        />
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
        algorithm: antdTheme.darkAlgorithm,
        ...antdConfig,
      }}
    >
      <BrowserRouter>
        <WatchlistProvider>
          <AppRoutes isDark={isDark} onThemeToggle={toggleTheme} />
        </WatchlistProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
