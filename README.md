# Prompt 管理器 （Prompt Manager）

语言: 简体中文 | [English](README.en.md)

一个功能完整的本地提示词管理系统，支持版本控制、搜索、标签管理、导入导出功能。采用Python + Flask + SQLite 构建，无需外部依赖，开箱即用。

A fully functional local prompt management system that supports version control, search, tag management, and import/export features. Built with Python + Flask + SQLite, it requires no external dependencies and works out of the box.

## ✨ 核心功能

### 📝 提示词管理
- **创建编辑**：支持名称、来源、标签、备注等完整元信息
- **内容预览**：首页显示内容摘要，支持一键复制完整内容
- **置顶功能**：重要提示词可置顶显示
- **智能搜索**：支持名称、来源、备注、标签、内容的全文搜索
- **语言切换**：支持中/英切换

### 🔄 版本控制系统
- **语义化版本**：遵循 `主版本.次版本.补丁版本` 格式
- **灵活升级**：支持补丁版本(+0.0.1)、次版本(+0.1.0)、主版本(+1.0.0)升级
- **历史回滚**：可从任意历史版本创建新版本，不覆盖原有数据
- **自动清理**：可设置版本保留阈值(默认200)，自动清理旧版本

### 📊 对比分析
- **Diff视图**：左右并排显示版本差异
- **词级对比**：精确到词汇级别的变更高亮(默认)
- **行级对比**：支持传统行级别的 diff 视图
- **快速切换**：词级/行级对比模式一键切换

### 🏷️ 标签系统
- **层级标签**：支持 `场景/客服` 这样的层级分类
- **智能联想**：输入时自动提示已有标签
- **多维度筛选**：支持按标签排序和筛选

### 🎨 用户体验
- **双主题支持**：浅色/深色主题，自动跟随系统
- **响应式设计**：完美适配桌面端和移动端
- **流畅动画**：精心设计的交互动画和过渡效果
- **键盘快捷键**：支持 Ctrl+S 保存、Ctrl+P 预览等快捷操作
- **桌面端视图切换**：首页支持列表/网格一键切换，并记住偏好
- **提示词颜色标注（新）**：在“高级设置”为提示词设置颜色（支持 #RGB/#RRGGBB），首页卡片将显示细微的同色外圈；提供可视化取色器、小圆点预览与“一键清除”按钮；留空则不设置
 - **界面语言（新）**：在“设置”中可切换界面语言（中文/英文），默认中文

### 📤 数据管理
- **导入导出**：JSON 格式完整数据备份和恢复
- **数据安全**：本地 SQLite 存储，无云端依赖
- **设置管理**：可配置版本清理阈值与访问密码等系统参数
  - 支持切换界面语言（中文/英文）

### 🔒 访问密码（可选）
- 三选一模式（设置页）：关闭 / 指定提示词密码 / 全局密码
- 密码要求：4–8 位，首次启用需先设置密码
- 指定提示词密码：在提示词编辑页勾选“该提示词需要密码访问”
- 首页行为（指定提示词密码模式）：受保护卡片仅显示标题与“来源：需要密码”，不展示标签、备注与内容预览；点击卡片进入解锁页
- 会话解锁：本次会话内对已解锁的提示词放行；可通过右上角“退出”清除认证

## 🚀 快速开始

### 方式一：Docker 运行 (推荐)

#### 环境要求
- Docker 和 Docker Compose

#### 使用官方镜像

- **镜像地址**：`docker.io/zhuchenyu2008/prompt-manage:latest`

```bash
# 拉取镜像
docker pull zhuchenyu2008/prompt-manage:latest

# 运行容器（持久化数据到名为 prompt-data 的卷）
docker run -d \
  --name prompt-manage \
  -p 3501:3501 \
  -v prompt-data:/app/data \
  zhuchenyu2008/prompt-manage:latest

# 访问应用
# http://localhost:3501
```



#### 使用 Docker Compose

1. **克隆项目**
   ```bash
   git clone https://github.com/zhuchenyu2008/prompt-manage
   cd prompt
   ```

2. **启动应用（本地构建）**
   ```bash
   # 启动服务
   docker-compose up
   # 或后台运行
   docker-compose up -d
   ```
   访问：http://localhost:3501

3. **使用以构建的镜像（生产推荐）**
   若希望直接使用已发布的官方镜像，可将 `docker-compose.yml` 中的 `build:` 替换为：
   ```yaml
   services:
     prompt-manager:
       image: zhuchenyu2008/prompt-manage:latest
       ports:
         - "3501:3501"
       volumes:
         - prompt-data:/app/data
       environment:
         - FLASK_ENV=production
       restart: unless-stopped
   ```

#### 使用单独的 Docker

```bash
# 构建镜像（本地开发场景）
docker build -t prompt-manager .

# 运行容器
docker run -d -p 3501:3501 -v prompt-data:/app/data prompt-manager
```


### 方式二：本地 Python 运行

#### 环境要求
- Python 3.9+
- Flask 框架及相关依赖

#### 安装运行

1. **克隆或下载项目**
   ```bash
   git clone https://github.com/zhuchenyu2008/prompt-manage
   cd prompt
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动应用**
   ```bash
   python app.py
   ```

4. **访问应用**
   打开浏览器访问：http://localhost:3501

> 注意：应用会在首次运行时自动创建数据库文件。
> - 容器/Compose 环境：默认路径为 `/app/data/data.sqlite3`（已挂载为持久化卷），无需额外配置。
> - 本地直跑（非 Docker）：请通过环境变量覆盖路径，例如 `DB_PATH=./data.sqlite3 python app.py`，数据库将创建在项目根目录。

## 📁 项目结构

```
prompt/
├── app.py              # Flask 应用主文件
├── requirements.txt    # Python 依赖文件
├── data.sqlite3        # 本地运行时可选的数据库文件（通过 DB_PATH 指向）
├── Dockerfile          # Docker 镜像配置
├── docker-compose.yml  # Docker Compose 配置文件
├── .dockerignore       # Docker 构建忽略文件
├── templates/          # HTML 模板
│   ├── layout.html     # 基础布局模板
│   ├── index.html      # 首页（卡片/列表切换 + 预览）
│   ├── prompt_detail.html # 详情页(编辑页面)
│   ├── versions.html   # 版本历史页面
│   ├── diff.html       # 对比页面
│   ├── settings.html   # 设置页面
│   └── auth.html       # 登录/解锁页面（访问密码）
├── static/             # 静态资源
│   ├── css/
│   │   └── style.css   # 样式文件
│   └── js/
│       └── main.js     # 前端脚本
└── README.md           # 项目说明文档
```

## 🗄️ 数据库结构

### 表结构
- **prompts**: 提示词基本信息
  - `id`, `name`, `source`, `notes`, `color`, `tags`, `pinned`, `created_at`, `updated_at`, `current_version_id`, `require_password`
- **versions**: 版本历史记录
  - `id`, `prompt_id`, `version`, `content`, `created_at`, `parent_version_id`
- **settings**: 系统设置
  - `key`, `value`
  - 关键键值：
    - `version_cleanup_threshold`：版本保留阈值（默认 200）
    - `auth_mode`：访问密码模式（`off` | `per` | `global`）
    - `auth_password_hash`：访问密码的 SHA-256 哈希

### 数据导出示例

```json
{
  "prompts": [
    {
      "id": 1,
      "name": "客服助手",
      "source": "ChatGPT",
      "notes": "处理客户咨询的标准回复模板",
      "color": "#409eff",
      "tags": ["场景/客服", "业务/售后"],
      "pinned": true,
      "require_password": false,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-02T12:34:56",
      "current_version_id": 3,
      "versions": [
        {
          "id": 1,
          "prompt_id": 1,
          "version": "1.0.0",
          "content": "你是一个专业的客服助手...",
          "created_at": "2024-01-01T00:00:00",
          "parent_version_id": null
        }
      ]
    }
  ]
}
```

## 🎯 使用指南

### 基本操作

1. **创建提示词**
   - 点击首页"新建提示词"按钮
   - 填写名称、来源等信息
   - 编写提示词内容
   - 选择版本升级类型并保存

2. **版本管理**
   - 编辑时勾选"保存为新版本"创建版本历史
   - 在详情页查看所有版本历史
   - 可对比任意两个版本的差异
   - 支持从历史版本回滚

3. **搜索和筛选**
   - 使用首页搜索框进行全文搜索
   - 支持按创建时间、修改时间、名称、标签排序
   - 置顶重要提示词便于快速访问

### 高级功能

- **标签系统**：使用 `/` 创建层级标签，如 `部门/技术/开发`
- **批量操作**：通过导入导出功能进行批量数据管理
- **版本对比**：支持词级和行级两种对比模式
- **主题切换**：点击右上角主题按钮切换深色/浅色模式
 - **颜色导入导出**：导出 JSON 包含 `color` 字段；导入时自动识别与校验（非法值忽略），留空按未设置处理
 
### 访问密码设置
1. 打开“设置 → 访问密码”。
2. 设置/修改密码（4–8 位）。
3. 选择模式：
   - 指定提示词密码：在提示词编辑页勾选“该提示词需要密码访问”。
   - 全局密码：开启后访问任意页面均需先登录。
4. 首页在“指定提示词密码”模式下会隐藏受保护提示词的标签、备注和内容，仅显示“来源：需要密码”；点击卡片可解锁。

### 首页视图切换（桌面端）
- 位置：提示词统计栏下方、列表上方的圆角小按钮。
- 图标：网格视图 `fa-table-cells` 与列表视图 `fa-list` 两个图标来回切换。
- 默认：网格视图（卡片式布局，自动自适应列数）。
- 记忆：切换结果会保存在 `localStorage.viewMode` 中，刷新后仍保持。
- 移动端：为保证阅读性，隐藏切换按钮且强制单列显示。

## ⚙️ 系统配置

### 端口配置
默认监听端口 `3501`，可在 `app.py` 中修改：
```python
app.run(host='0.0.0.0', port=3501, debug=True)
```

### 版本清理策略
- 默认每个提示词保留最新 200 个版本
- 超出限制时自动删除最旧的版本
- 可在设置页面调整此阈值

### 安全与注意事项
- 访问密码为轻量级访问控制，密码以 SHA-256 存储，无盐；请勿用于高安全场景。
- 忘记密码可通过 SQLite 工具清除：
  ```sql
  -- 使用 sqlite3 打开数据库后执行
  DELETE FROM settings WHERE key='auth_password_hash';
  UPDATE settings SET value='off' WHERE key='auth_mode';
  ```
  清除后重启应用并在设置页重新配置。

## 🛠️ 开发说明

### 技术栈
- **后端**: Flask (Python Web 框架)
- **数据库**: SQLite (轻量级本地数据库)
- **前端**: 原生 HTML/CSS/JavaScript
- **样式**: CSS 变量 + Flexbox/Grid 布局
- **图标**: Font Awesome
- **依赖**: Flask, Werkzeug

### 特色实现
- **主题系统**: 使用 CSS 变量和 `data-theme` 属性
- **响应式设计**: 移动优先的响应式布局
- **无依赖构建**: 纯静态资源，无需构建工具
- **数据持久化**: localStorage 保存用户偏好设置

## 🔧 故障排除

### 常见问题
1. **依赖缺失**：运行 `pip install flask` 安装 Flask 框架
2. **端口占用**：修改 `app.py` 中的端口号
3. **权限问题**：确保对当前目录有读写权限
4. **数据库损坏**：删除 DB_PATH 指向的数据库文件后重新生成（容器默认 `/app/data/data.sqlite3`；本地示例 `./data.sqlite3`）

### 重置系统
如需重置所有数据，删除 DB_PATH 指向的数据库文件后重启应用即可（容器默认 `/app/data/data.sqlite3`；本地示例 `./data.sqlite3`）。

## 配置说明

- DB_PATH: 指定 SQLite 数据库文件路径
  - 容器/Compose 默认：`/app/data/data.sqlite3`
  - 本地运行示例：`DB_PATH=./data.sqlite3 python app.py`
  - 未设置时使用默认值；应用会在首次访问时自动创建目录与数据库文件

## 📝 更新日志

### 最新功能
- ✅ 新增提示词颜色标注：在“高级设置”可设置颜色（#RGB/#RRGGBB），首页卡片显示细微彩色外圈；内置可视化取色器、预览圆点与清除按钮；导入/导出完整支持 `color` 字段
- ✅ 首页卡片式网格布局 + 桌面端视图开关
- ✅ 完善的黑夜模式适配
- ✅ 首页内容预览一键复制
- ✅ 动态页面标题显示
- ✅ 简化的用户界面
- ✅ 增强的颜色主题系统
 - ✅ 新增访问密码（关闭/指定提示词/全局）与卡片加锁显示

### 变更与修复
- 统一使用相对路径作为 `next`
  - 在全局密码拦截中将 `next` 从 `request.url` 改为相对路径（如 `/settings?...`），避免出现 `http://127.0.0.1` 这类内部地址。
  - 在登录与解锁处理中对 `next` 做安全归一化，只允许站内相对路径，防止外部跳转导致失败或安全风险。
- 信任反向代理的头
  - 加入 `ProxyFix`，尊重 `X-Forwarded-Proto/Host` 等头，确保 `request.host`/`request.url` 能反映真实外网域名与协议。
- 修复设置页未授权修改密码的逻辑漏洞，避免任意用户可进入设置修改密码。
