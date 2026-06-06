# IMS Games

透明、可解释、可扩展的游戏评分聚合系统。

Transparent, explainable, and extensible game score aggregation system.

## 在线访问

**https://tylevnovik.github.io/ims-games/**

## 功能特性

### 游戏库（/games）
- 12,660+ 款游戏，支持搜索、年份/类型/平台筛选、多列排序
- 每款游戏展示 IMS 原始分、稳健分、校准分、加权分及 Metacritic 基准分
- 开发者、发行商、类型、平台、简介等元数据（由 RAWG 数据集补全）

### 游戏详情页（/games/{id}）
- 分数分布柱状图（0-100 十档，显示均值与评论数）
- 评论表格：内联搜索、语言/平台筛选、点击列头排序
- 自定义评分权重面板：语言筛选、平台筛选、排除异常值、降低/提升媒体权重
- 外部基准分数对比（Metacritic、RAWG Metacritic）
- 语言分布与平台分布可视化

### GOAT — 史上最伟大游戏（/goat）
- 基于 IMS 加权分排名，#1 以金色奖杯卡片高亮展示
- Top 2-50 候选排行表格，可跳转游戏详情

### GOTY — 年度游戏（/goty）
- 覆盖 2014–2023 年，对比三大颁奖典礼年度游戏得主：
  - **The Game Awards (TGA)**：含提名列表
  - **BAFTA Games Awards**
  - **GDC Game Developers Choice Awards**
- 自动检测同年多奖"共识"游戏
- IMS 年度 Top 10 排名，获奖游戏行高亮标注
- 颁奖数据经 Wikipedia 核实

### 其他页面
- **媒体源**（/sources）：500+ 家评论媒体及其历史表现指标
- **算法说明**（/methodology）：四种 IMS 分数类型的计算公式
- **数据来源**（/data-sources）：数据源、采集方式与版权说明

### 通用
- 中英双语（zh/en），语言切换持久化
- 移动端响应式设计（汉堡菜单、触摸优化、表格横向滚动）

## 技术栈

- **前端**：Astro 5 + React 19 + TypeScript + Tailwind CSS 3
- **数据处理**：Python 3.11+、pandas、SQLite（通过 uv 管理）
- **部署**：GitHub Pages + GitHub Actions 自动化构建
- **数据库存储**：GitHub Release（SQLite 文件，CI 自动下载）

## 数据源

| 来源 | 内容 | 规模 |
|------|------|------|
| Metacritic Kaggle 数据集 | 评论分数、游戏标题 | 12,660 游戏 / 321,000 评论 |
| RAWG 数据集 | 开发者、发行商、类型、平台、简介、发行日期 | 889,000 游戏（匹配 11,997 款） |
| GOTY 颁奖数据 | TGA / BAFTA / GDC 年度最佳 | 2014–2023（人工整理） |

## 数据管线

```bash
# 1. 初始化数据库
uv run python scripts/init_db.py

# 2. 导入 Metacritic Kaggle 数据
uv run python scripts/import_metacritic_kaggle.py

# 3. 归一化分数
uv run python scripts/normalize_scores.py

# 4. 计算游戏分数（IMS raw / robust / calibrated / weighted）
uv run python scripts/compute_game_scores.py

# 5. 计算媒体指标
uv run python scripts/compute_source_metrics.py

# 6. 计算媒体权重
uv run python scripts/compute_weights.py

# 7. RAWG 数据补全（两轮匹配）
uv run python scripts/enrich_from_rawg.py
uv run python scripts/enrich_from_rawg_v2.py

# 8. 回填评论平台数据
uv run python scripts/backfill_review_platforms.py

# 9. 导出静态 JSON
uv run python scripts/export_static_json.py

# 一键执行完整管线
uv run python scripts/build_all.py
```

## 本地开发

```bash
# 安装 Python 依赖
uv sync

# 运行数据管线（生成 public/data/*.json）
uv run python scripts/build_all.py

# 安装前端依赖
cd site && npm install

# 本地开发服务器
npm run dev

# 生产构建
npm run build
```

## 项目结构

```
├── scripts/                    # 数据处理管线
│   ├── config.py               # 配置（DB 路径、算法版本）
│   ├── init_db.py              # 初始化 SQLite 数据库
│   ├── import_metacritic_kaggle.py  # 导入 Kaggle 数据
│   ├── normalize_scores.py     # 分数归一化
│   ├── compute_game_scores.py  # IMS 分数计算
│   ├── compute_source_metrics.py    # 媒体指标
│   ├── compute_weights.py      # 媒体权重
│   ├── enrich_from_rawg.py     # RAWG 匹配 v1
│   ├── enrich_from_rawg_v2.py  # RAWG 匹配 v2（模糊匹配）
│   ├── backfill_review_platforms.py # 评论平台回填
│   └── export_static_json.py   # 导出前端静态数据
├── site/                       # Astro 前端
│   ├── src/
│   │   ├── components/         # React 组件
│   │   │   ├── GameList.tsx         # 游戏列表（筛选/排序/分页）
│   │   │   ├── GameDetailClient.tsx  # 游戏详情（客户端渲染）
│   │   │   ├── ReviewTable.tsx       # 评论表格（搜索/筛选/排序）
│   │   │   ├── ScoreDistributionChart.tsx  # 分数分布图
│   │   │   ├── CustomWeightPanel.tsx       # 自定义权重面板
│   │   │   ├── GoatList.tsx          # GOAT 排行组件
│   │   │   └── GotyList.tsx          # GOTY 对比组件
│   │   ├── lib/
│   │   │   ├── types.ts             # TypeScript 类型定义
│   │   │   ├── i18n.ts             # 国际化翻译字典
│   │   │   ├── score.ts            # 分数计算逻辑（客户端）
│   │   │   ├── base.ts             # 基础路径工具
│   │   │   └── awards-data.ts      # GOTY 颁奖数据
│   │   ├── layouts/Layout.astro     # 全局布局（导航/页脚/语言切换）
│   │   └── pages/
│   │       ├── index.astro          # 首页
│   │       ├── games/index.astro    # 游戏库
│   │       ├── games/[game_id].astro # 游戏详情
│   │       ├── goat.astro           # GOAT 页面
│   │       ├── goty.astro           # GOTY 页面
│   │       ├── sources/index.astro  # 媒体源列表
│   │       ├── sources/[source_id].astro # 媒体详情
│   │       ├── methodology.astro    # 算法说明
│   │       └── data-sources.astro   # 数据来源
│   └── public/data/            # 静态 JSON 数据（由管线生成）
├── .github/workflows/          # GitHub Actions CI/CD
└── README.md
```

## IMS 评分算法

| 分数类型 | 计算方式 |
|---------|---------|
| **IMS Raw** | 所有归一化评论分数的简单均值 |
| **IMS Robust** | 截尾均值（去除最高/最低 5%），需 ≥20 条评论 |
| **IMS Calibrated** | z-score 校准，调整每个媒体的评分倾向 |
| **IMS Weighted** | 加权均值，权重基于样本量、区分度、类型/平台相关性 |

所有分数统一归一化至 0–100 量表。详细公式见 [/methodology](https://tylevnovik.github.io/ims-games/methodology/) 页面。

## License

本项目为研究与演示目的。游戏评分数据来自公开数据集，原始评分归属于相应媒体。
