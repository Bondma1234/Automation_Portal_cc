"""Pydantic 请求模型（路由层入参校验）。

响应统一用 dict（SQLite Row 转换），不额外建响应模型，减少样板代码。
"""
from typing import List
from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    username: str
    password: str


class CaseBody(BaseModel):
    """新增功能用例（自动化状态不入参 —— 由脚本映射自动判定）"""
    id: str = Field(min_length=1, description="用例编号，主键")
    app: str
    module: str
    priority: str = "P0"


class TaskBody(BaseModel):
    """新建测试任务：App 范围 × 品牌范围 + 用例范围 + 执行方式"""
    name: str = Field(min_length=1)
    apps: List[str] = Field(min_length=1)
    brands: List[str] = Field(min_length=1)
    scope: str = "全部用例"          # 全部用例 / 仅 P0 / 仅 P1
    mode: str = "多品牌并行"          # 多品牌并行 / 串行


class RunBody(BaseModel):
    """执行中心发起执行：device_ids=点名的真机台架（一台一列）；brands=模拟品牌列/旧路径"""
    task: str                        # 任务名
    brands: List[str] = []
    device_ids: List[int] = []


class RunScriptBody(BaseModel):
    """脚本管理页发起执行（按脚本跑其对应框架的用例）"""
    brands: List[str] = []
    device_ids: List[int] = []


class SettingsBody(BaseModel):
    webhook: str = ""
    notify_fail: bool = True
    notify_daily: bool = True


class AppBody(BaseModel):
    """接入被测 App：包名/Activity/版本/测试账号登记"""
    name: str = Field(min_length=1)
    package: str = Field(min_length=1)
    activity: str = ""
    version: str = "—"
    account: str = "—"


class DeviceBody(BaseModel):
    """接入台架：udid 即 adb serial（网络设备 ip:5555），入库即进该品牌执行设备池"""
    name: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    udid: str = Field(min_length=1)
    resolution: str = "—"
    os: str = "—"
