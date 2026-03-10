/**
 * 前端版本号
 * 每次发布更新时修改此版本号
 */
export const FRONTEND_VERSION = '1.0.0';

/**
 * 构建时间
 */
export const BUILD_TIME = new Date().toISOString();

/**
 * 获取完整版本信息
 */
export const getVersionInfo = () => ({
  frontend: FRONTEND_VERSION,
  buildTime: BUILD_TIME,
});
