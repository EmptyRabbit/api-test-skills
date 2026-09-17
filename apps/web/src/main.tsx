import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createRoot } from 'react-dom/client';
import App from './App';
import './monacoSetup';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <ConfigProvider
    locale={zhCN}
    theme={{
      token: {
        colorPrimary: '#3d6bff',
        colorText: '#1c1c1e',
        colorBgLayout: '#eef0f6',
        borderRadius: 8,
        fontFamily: '"Segoe UI Variable", "Segoe UI", system-ui, sans-serif',
      },
    }}
  >
    <AntdApp>
      <App />
    </AntdApp>
  </ConfigProvider>
);
