import axios from 'axios';
import { setupAuthInterceptor } from './auth';

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

setupAuthInterceptor(request);

export interface VersionInfo {
  version: string;
  build_time: string;
  commit: string;
}

// 获取后端版本号
export const getBackendVersion = () => {
  return request.get('/version');
};
