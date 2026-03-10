import React, { useEffect, useState } from 'react';
import { Tag, Tooltip, Space } from 'antd';
import { FRONTEND_VERSION, BUILD_TIME } from '../../version';
import { getBackendVersion } from '../../services/versionApi';

interface VersionInfo {
  version: string;
  build_time: string;
  commit: string;
}

export const VersionDisplay: React.FC = () => {
  const [backendVersion, setBackendVersion] = useState<VersionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const res = await getBackendVersion();
        if (res.data?.success) {
          setBackendVersion(res.data.data);
        }
      } catch (error) {
        console.error('Failed to fetch backend version:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVersion();
  }, []);

  const formatBuildTime = (timeStr: string) => {
    try {
      const date = new Date(timeStr);
      return date.toLocaleString('zh-CN');
    } catch {
      return timeStr;
    }
  };

  return (
    <Space size="small">
      <Tooltip
        title={
          <div style={{ fontSize: 12 }}>
            <div>前端版本: {FRONTEND_VERSION}</div>
            <div>构建时间: {formatBuildTime(BUILD_TIME)}</div>
            {backendVersion && (
              <>
                <div style={{ marginTop: 8, borderTop: '1px solid #333', paddingTop: 8 }}>
                  <div>后端版本: {backendVersion.version}</div>
                  <div>构建时间: {formatBuildTime(backendVersion.build_time)}</div>
                  <div>Commit: {backendVersion.commit}</div>
                </div>
              </>
            )}
          </div>
        }
      >
        <Tag color="default" style={{ cursor: 'help', fontSize: 11 }}>
          FE: {FRONTEND_VERSION}
          {backendVersion && ` | BE: ${backendVersion.version}`}
        </Tag>
      </Tooltip>
    </Space>
  );
};


