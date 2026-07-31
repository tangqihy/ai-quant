/**
 * 鉴权：token 存储与 axios 拦截器（自动带 token、401 跳转登录）
 */

const TOKEN_KEY = 'quant_auth_token';

/** token 变更事件：localStorage 本身非响应式，登录/登出后需主动通知订阅方 */
export const AUTH_CHANGED_EVENT = 'quant-auth-changed';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

/** 登录页路径（与 React Router basename 一致） */
const LOGIN_PATH = '/quant/login';

/** 收到 401 时跳转登录页 */
export function redirectToLogin(): void {
  clearToken();
  const base = typeof window !== 'undefined' ? window.location.origin : '';
  window.location.href = `${base}${LOGIN_PATH}`;
}

/**
 * 为 axios 实例注册请求/响应拦截器：
 * - 请求：自动添加 Authorization: Bearer <token>
 * - 响应：401 时清除 token 并跳转登录页
 */
export function setupAuthInterceptor(axiosInstance: import('axios').AxiosInstance): void {
  axiosInstance.interceptors.request.use((config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  axiosInstance.interceptors.response.use(
    (res) => res,
    (err) => {
      const url = err?.config?.url ?? '';
      if (err?.response?.status === 401 && !String(url).includes('/auth/login')) {
        redirectToLogin();
      }
      return Promise.reject(err);
    }
  );
}
