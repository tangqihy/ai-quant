import React, { useMemo, useState } from 'react';
import { Button, Dropdown, Input, Space, Tag, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { DownOutlined, StarOutlined } from '@ant-design/icons';
import { useWatchlist } from '../../hooks/useWatchlist';

const { Text } = Typography;

export interface SymbolInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  allowClear?: boolean;
  size?: 'small' | 'middle' | 'large';
  style?: React.CSSProperties;
  /** 紧凑：适合工具条一行布局 */
  compact?: boolean;
  className?: string;
}

/** 阻止菜单 mousedown 导致 Input 失焦，否则选中 click 会被吃掉 */
function preventInputBlur(menu: React.ReactNode) {
  return <div onMouseDown={(e) => e.preventDefault()}>{menu}</div>;
}

/**
 * 股票代码输入：可手输，也可从自选选取。
 * 表单值始终为代码；匹配自选时旁边展示中文名。
 */
const SymbolInput: React.FC<SymbolInputProps> = ({
  value,
  onChange,
  placeholder = '输入代码或从自选选择',
  disabled,
  allowClear = true,
  size = 'middle',
  style,
  compact = false,
  className,
}) => {
  const { stocks, isLoaded, getStock } = useWatchlist();
  const [suggestOpen, setSuggestOpen] = useState(false);

  const pick = (symbol: string) => {
    const next = String(symbol || '').trim();
    if (!next || next.startsWith('_')) return;
    onChange?.(next);
    setSuggestOpen(false);
  };

  const matched = useMemo(() => {
    const code = String(value || '').trim();
    if (!code) return undefined;
    return getStock(code) || stocks.find((s) => s.symbol === code);
  }, [value, getStock, stocks]);

  const displayName = matched?.name?.trim() || '';

  const filtered = useMemo(() => {
    const q = String(value || '')
      .trim()
      .toLowerCase();
    if (!q) return stocks;
    return stocks.filter((s) => `${s.symbol} ${s.name || ''}`.toLowerCase().includes(q));
  }, [stocks, value]);

  const buildItems = (list: typeof stocks, emptyLabel: string): MenuProps['items'] => {
    if (list.length === 0) {
      return [{ key: '_empty', disabled: true, label: emptyLabel }];
    }
    return list.slice(0, 40).map((s) => ({
      key: s.symbol,
      label: (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, minWidth: 160 }}>
          <Text code style={{ margin: 0 }}>
            {s.symbol}
          </Text>
          <Text>{s.name || ''}</Text>
        </div>
      ),
    }));
  };

  const suggestItems = buildItems(
    filtered,
    stocks.length === 0
      ? isLoaded
        ? '暂无自选，可直接输入代码'
        : '自选加载中…'
      : '无匹配自选'
  );

  const watchlistItems = buildItems(stocks, isLoaded ? '暂无自选，请先添加' : '自选加载中…');

  const onMenuClick: MenuProps['onClick'] = ({ key }) => {
    pick(String(key));
  };

  const showSuggest =
    suggestOpen && !disabled && (filtered.length > 0 || (isLoaded && stocks.length === 0));

  return (
    <Space size={6} style={{ width: '100%', ...style }} className={className} wrap>
      <Space.Compact style={{ flex: 1, minWidth: compact ? 160 : 220 }} size={size}>
        <Dropdown
          menu={{ items: suggestItems, onClick: onMenuClick }}
          open={showSuggest}
          onOpenChange={setSuggestOpen}
          trigger={['click']}
          disabled={disabled}
          popupRender={preventInputBlur}
        >
          <Input
            value={value ?? ''}
            onChange={(e) => {
              onChange?.(e.target.value);
              setSuggestOpen(true);
            }}
            onFocus={() => setSuggestOpen(true)}
            onPressEnter={() => setSuggestOpen(false)}
            placeholder={placeholder}
            disabled={disabled}
            allowClear={allowClear}
            size={size}
            style={{ width: '100%', minWidth: compact ? 100 : 140 }}
          />
        </Dropdown>
        <Dropdown
          menu={{ items: watchlistItems, onClick: onMenuClick }}
          disabled={disabled || !isLoaded}
          trigger={['click']}
          popupRender={preventInputBlur}
        >
          <Button size={size} icon={<StarOutlined />} disabled={disabled}>
            {compact ? null : '自选'}
            <DownOutlined />
          </Button>
        </Dropdown>
      </Space.Compact>
      {displayName ? (
        <Tag color="cyan" style={{ margin: 0, fontSize: 13 }} title={displayName}>
          {displayName}
        </Tag>
      ) : null}
    </Space>
  );
};

export default SymbolInput;
