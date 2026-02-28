import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import StockList from './pages/StockList';
import BacktestConfig from './pages/BacktestConfig';
import Analysis from './pages/Analysis';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter basename="/quant">
        <MainLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stocks" element={<StockList />} />
            <Route path="/backtest" element={<BacktestConfig />} />
            <Route path="/analysis" element={<Analysis />} />
          </Routes>
        </MainLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
