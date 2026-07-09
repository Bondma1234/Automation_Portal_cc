# JDO 车机自动化测试平台

车机生态 App（酷我音乐 / 喜马拉雅 / 乐听 / 爱奇艺 / Launcher / 车内会议）跨品牌发版回归自动化平台：
**一次写用例、多品牌跑、自动出报告**，并量化自动化覆盖率与节省人力。

## 快速启动

```bat
:: 方式一：双击 start.bat
:: 方式二：命令行
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8770
```

访问 <http://127.0.0.1:8770> · 登录 `admin / 123456`
（⚠️ 端口 8765 被并行的 Codex 平台占用，本平台固定 **8770**）

首次启动自动建库并灌入演示种子数据；删除 `backend/data/jdo.db` 可重置。

## 工程结构（前后端分离 · 分层）

```
├─ backend/                 # FastAPI + SQLite 后端
│  └─ app/
│     ├─ main.py            #   入口：挂路由 + 托管前端静态
│     ├─ config.py          #   路径/端口/业务常量
│     ├─ db.py              #   数据层：建表 + 种子数据
│     ├─ models.py          #   Pydantic 请求模型
│     ├─ api/               #   路由层（薄：收参数→调服务→包装响应）
│     └─ services/          #   业务层（业务规则 + 执行引擎 + 多框架适配器 + 扫描器）
│                           #   run_service / runner_common / media_runner / zcode_runner
│                           #   official_service(官方导入+框架识别) / allure_service
├─ frontend/                # 免构建静态前端（改完刷新即生效）
│  ├─ index.html            #   外壳（与设计原型 DOM 一致）
│  ├─ css/                  #   设计 token + 组件样式（迁移自原型）
│  ├─ js/                   #   api/store/ui/theme/router 分层
│  │  └─ views/             #   每个模块一个视图文件（11 模块 + 登录）
│  └─ vendor/               #   Chart.js + Tabler 图标（已本地化，内网可用）
├─ framework/               # 我们自己的 pytest + uiautomator2 测试框架（脚本作者工作区）
│  ├─ config/  core/        #   平台组维护：设备/adb/页面基类
│  ├─ pages/   testcases/   #   脚本作者编写（见 doc/脚本框架规范.md）
│  └─ conftest.py           #   设备注入 + case 标记上报 + 失败现场采集
└─ doc/                     # 需求/原型/项目/上下文/脚本规范 文档
```

> 外部框架（Media_automation / Zcode）不进本仓库 —— 打成 zip 从「脚本管理」上传，
> 平台自动识别、解压缓存到 `backend/data/frameworks/`、按其映射接入覆盖率与执行。

## 核心机制

- **覆盖率口径**：业务用例覆盖率 = 已自动化用例 ÷ 全部手工用例；手工用例库由**官方测试报告 Excel 导入**
  （测试用例页「导入官方用例」），自动化状态由各框架的映射**自动判定**（统一收口 `script_case` 表），不允许手填。
  看板给「全量 + P1/P2 重点」双口径。
- **平台兼容多套自动化框架**（核心能力）：不强推平台自己的约定，每套框架写一个「适配器」接进来。当前支持：
  - 我们的 `framework/`（`@pytest.mark.case` 标记，u2）；
  - **Media_automation**（ADB-XML dump 驱动，docs CSV 映射）；
  - **Media_automation_Zcode**（u2 驱动，markdown 覆盖矩阵映射）。
  上传 zip 自动识别框架；共用执行内核 `runner_common`（解压/进度插件/实时点亮矩阵），各适配器只写映射解析 + 设备注入差异。
- **执行引擎**（`services/run_service.py`）：策略式 —— 品牌台架可达则真机跑该框架的 pytest（实时进度/Allure/落库），
  否则回退与原型节奏一致的模拟执行。两个入口：**按任务**（执行中心选任务，按覆盖最多的框架路由）、
  **按脚本**（脚本管理点「执行」，直接跑该脚本对应框架，不受路由）。
- **Allure 真报告**：真机执行由 pytest 产出结果，模拟/历史报告按明细合成；执行完后台预生成，点击秒开（依赖 allure CLI + Java）。
- **设计基准**：界面与交互以 `doc/原型-交互版.html` 为准，改前端先对照原型。

## 文档

| 文档 | 内容 |
|---|---|
| [doc/需求文档.md](doc/需求文档.md) | 背景 + 各模块需求与实现逻辑 |
| [doc/项目文档.md](doc/项目文档.md) | 技术架构、进度、开发顺序 |
| [doc/上下文.md](doc/上下文.md) | 既定决策与进度快照（跨会话续接） |
| [doc/脚本框架规范.md](doc/脚本框架规范.md) | **脚本作者必读**：目录约定 + 三条强制规则 |
