# ZhiWeave Frontend

React 19 + TypeScript + Vite 8 的知识库生产工作台。界面围绕数据导入与检索链路，而不是聊天框。

## 页面能力

- 知识库创建与切换。
- 网页入口、最大页数和 Celery 任务提交。
- PostgreSQL、Redis、Qdrant 服务状态。
- 文档、来源 URL、语言和抓取时间列表。
- Chunk 正文、字符数、序号和哈希查看器。
- 任务进度、当前阶段和失败原因。
- Query → Qdrant Top-K 检索实验室。
- 通用知识库 ZIP 下载。
- 使用真实项目截图编写的独立图文指南页。
- 可操作的项目配置面板、用户帮助菜单和移动端导航选择器。

## 页面路由

前端使用 React Router 的 `BrowserRouter`，每个工作区都有可以直接访问、刷新和分享的 URL：

| 路径 | 页面 |
| --- | --- |
| `/` | 知识库总览 |
| `/sources` | 数据源 |
| `/chunks` | Chunk 工作台 |
| `/retrieval` | 检索实验室 |
| `/tasks` | 任务队列 |
| `/export` | 导出 |
| `/guide` | 独立使用指南，不显示工作台左侧栏 |

浏览器前进、后退和刷新都会保留当前页面。部署时需要让 Web 服务器把这些前端路径回退到 `index.html`。

## 启动

```bash
cd ZhiWeave/frontend
nvm use 22.13.0
pnpm install --frozen-lockfile
pnpm dev --host 0.0.0.0
```

访问 `http://localhost:5173/`。开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 构建

```bash
pnpm build
```

## 视觉方向

- 暖白工作区、浅灰侧栏、靛蓝动作色和青绿色成功状态。
- 首屏直接暴露网址导入、模型/维度、Chunk 参数和处理流水线。
- 聊天生成层以后作为可选模块加入，不占据当前产品中心。
- 桌面、窄侧栏和平板/手机均有响应式布局。
