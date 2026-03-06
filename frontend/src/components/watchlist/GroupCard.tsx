import React from 'react';
import { Card, Badge, Space, Button, Typography, Tag } from 'antd';
import {
  FolderOutlined,
  EditOutlined,
  DeleteOutlined,
  StockOutlined,
} from '@ant-design/icons';
import { WatchlistGroup, WatchlistItem } from '../../types/watchlist';

const { Text } = Typography;

interface GroupCardProps {
  group: WatchlistGroup;
  stocks: WatchlistItem[];
  isActive?: boolean;
  onClick?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

export const GroupCard: React.FC<GroupCardProps> = ({
  group,
  stocks,
  isActive,
  onClick,
  onEdit,
  onDelete,
}) => {
  return (
    <Card
      hoverable
      onClick={onClick}
      style={{
        borderRadius: 12,
        borderColor: isActive ? group.color : undefined,
        boxShadow: isActive ? `0 0 0 2px ${group.color}40` : undefined,
        cursor: onClick ? 'pointer' : 'default',
      }}
      bodyStyle={{ padding: 16 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            backgroundColor: `${group.color}20`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <FolderOutlined style={{ fontSize: 24, color: group.color }} />
        </div>
        
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text strong style={{ fontSize: 16, display: 'block' }}>
            {group.name}
          </Text>
          <Space size={4} style={{ marginTop: 4 }}>
            <StockOutlined style={{ fontSize: 12, color: '#8c8c8c' }} />
            <Text type="secondary" style={{ fontSize: 13 }}>
              {stocks.length} 只股票
            </Text>
          </Space>
        </div>

        <Space>
          {onEdit && (
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
            />
          )}
          {onDelete && (
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
            />
          )}
        </Space>
      </div>

      {/* 显示前几个股票的标签 */}
      {stocks.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {stocks.slice(0, 3).map(stock => (
            <Tag key={stock.symbol} size="small">
              {stock.name}
            </Tag>
          ))}
          {stocks.length > 3 && (
            <Tag size="small">+{stocks.length - 3}</Tag>
          )}
        </div>
      )}
    </Card>
  );
};
