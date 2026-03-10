"""
自选数据模型
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WatchlistGroup(BaseModel):
    """自选分组"""
    id: str = Field(..., description="分组ID")
    name: str = Field(..., description="分组名称")
    color: str = Field(default="#1890ff", description="分组颜色")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class WatchlistItem(BaseModel):
    """自选股票"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(default="", description="股票名称")
    group_ids: List[str] = Field(default_factory=list, description="所属分组ID列表")
    note: str = Field(default="", description="备注")
    created_at: datetime = Field(default_factory=datetime.now, description="添加时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class WatchlistData(BaseModel):
    """自选数据"""
    groups: List[WatchlistGroup] = Field(default_factory=list, description="分组列表")
    stocks: List[WatchlistItem] = Field(default_factory=list, description="股票列表")


class CreateGroupRequest(BaseModel):
    """创建分组请求"""
    name: str = Field(..., description="分组名称")
    color: str = Field(default="#1890ff", description="分组颜色")


class AddStockRequest(BaseModel):
    """添加股票请求"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(default="", description="股票名称")
    group_ids: List[str] = Field(default_factory=list, description="分组ID列表")
    note: str = Field(default="", description="备注")


class UpdateStockRequest(BaseModel):
    """更新股票请求"""
    group_ids: Optional[List[str]] = Field(None, description="分组ID列表")
    note: Optional[str] = Field(None, description="备注")


class RenameGroupRequest(BaseModel):
    """重命名分组请求"""
    name: str = Field(..., description="新名称")
