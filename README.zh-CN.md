# AirTrip — 航线运营 API

[English](README.md) · **简体中文**

一个用来浏览航司运营数据、给个人行程排航线的 REST API。后端是 Flask
应用（Flask-RESTX 出 Swagger 文档、SQLAlchemy 做持久化、Flask-JWT-Extended
管登录），数据存在本地 SQLite 里，首次运行时在代码旁边自动创建。

## 功能

- **账号与鉴权** —— JWT bearer token，分 `admin` / `user` 两种角色；管理员
  可以创建、列出、停用和删除账号。停用立刻生效，因为每次请求都会重新校验
  账号状态。
- **CSV 导入** —— 上传 `airports.csv`、`airlines.csv`、`routes.csv`（单独或
  一起传都行）。每个文件逐格校验，合并后再做一次内部一致性和引用完整性检查。
  如果某个已有行程还引用着某条要被删掉的航线，替换 `routes` 会返回 `409`，
  避免用户数据被静默抹掉。
- **数据浏览** —— 机场、航司、航线都支持分页、筛选、大小写不敏感搜索；机场
  和航司能列出自己的航线，航线详情里带上两端的机场。
- **行程计划** —— 带名称和日期区间的私有航线集合。每个行程只属于一个账号，
  其他人（包括管理员）都看不到。
- **导出** —— 可以把行程导出成独立的 JSON 附件，或渲染成 PNG 时间线。
- **Swagger UI** 挂在 `/docs`，可以逐个端点在页面上试。
- **Web 客户端** 挂在 `/app` —— 同一套 API 之上的单页应用：Frutiger Aero
  风格的航线网络浏览器（机场、航司、航线）、带航线选择器的私有行程、账号
  管理以及 CSV 导入。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `airtrip_api.py` | 整个应用：数据模型、工具函数、资源类、Swagger 模型。 |
| `airtrip_tests.py` | 黑盒 pytest 测试，通过 HTTP 驱动一个正在运行的服务。 |
| `airlines.csv`、`airports.csv`、`routes.csv` | 供导入器使用的示例数据集。 |
| `requirements.txt` | 依赖清单。 |
| `airtrip.db` | SQLite 数据库，首次运行时生成。 |
| `airtrip-web/` | Vue 3 + Vite + TypeScript 单页客户端（`dist/` 由 Flask 托管）。 |

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python airtrip_api.py          # Swagger UI: http://127.0.0.1:5000/docs
```

API 同时托管 Web 客户端：<http://127.0.0.1:5000/app/>。构建产物在
`airtrip-web/dist`，改了前端之后重新构建即可：

```bash
cd airtrip-web
npm install
npm run build        # 生产包，由 Flask 在 /app/ 提供
npm run dev          # 或者：热更新开发服务器 http://127.0.0.1:5173/app/
```

首次运行会种两个账号：`admin` / `admin` 和 `user` / `user`。调
`POST /api/auth/login` 拿到 token，在 Swagger 里点 **Authorize** 粘贴进去，
再以管理员身份导入数据集：

```bash
curl -X POST http://127.0.0.1:5000/api/import \
  -H "Authorization: Bearer <admin token>" \
  -F "airports=@airports.csv" \
  -F "airlines=@airlines.csv" \
  -F "routes=@routes.csv"
```

对外暴露服务之前，请把 `AIRTRIP_JWT_SECRET` 设成真正的密钥——内置默认值只是
开发用的占位符。

## Web 客户端

| 路由 | 页面 |
| --- | --- |
| `/app/login` | 登录（账号见上）。 |
| `/app/dashboard` | 各类计数、快捷入口、最近新增机场、最后一次导入。 |
| `/app/airports`、`/app/airports/:iata` | 可搜索列表；机场详情含航线、航司、目的地。 |
| `/app/airlines`、`/app/airlines/:iata` | 航司目录，以及每家航司执飞的航线。 |
| `/app/routes` | 航线浏览器，点开是详情抽屉。 |
| `/app/plans`、`/app/plans/new`、`/app/plans/:id/edit` | 私有行程，带航线选择器和 JSON/PNG 导出。 |
| `/app/users`、`/app/import` | 管理员专用：账号管理与 CSV 导入。 |

`/app/style-tile` 是设计系统的可视化说明页（活的样式规范）。

## 测试

```bash
rm -f airtrip.db               # 从空库开始
python airtrip_api.py          # 一个终端跑服务
pytest airtrip_tests.py -v     # 另一个终端跑测试（47 个）
```

测试只通过 HTTP 与服务对话，从不 import 应用本体，所以它验证的就是客户端
真实能看到的东西。要指向别的端口，用
`API_BASE_URL=http://127.0.0.1:5056`。

## 接口概览

`/api/auth` · `/api/users` · `/api/import` · `/api/airports` · `/api/airlines`
· `/api/routes` · `/api/plans`（含 `/api/plans/export`）
