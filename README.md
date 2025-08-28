# Prompt 管理器

一个功能完整的本地提示词管理系统，支持版本控制、搜索、标签管理、导入导出等功能。采用 Python + Flask + SQLite 构建，无需外部依赖，开箱即用。

## ✨ 核心功能

### 📝 提示词管理
- **创建编辑**：支持名称、来源、标签、备注等完整元信息
- **内容预览**：首页显示内容摘要，支持一键复制完整内容
- **置顶功能**：重要提示词可置顶显示
- **智能搜索**：支持名称、来源、备注、标签、内容的全文搜索

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
- **双主题支持**：浅色/深色主题，自动跟随系统偏好
- **响应式设计**：完美适配桌面端和移动端
- **流畅动画**：精心设计的交互动画和过渡效果
- **键盘快捷键**：支持 Ctrl+S 保存、Ctrl+P 预览等快捷操作

### 📤 数据管理
- **导入导出**：JSON 格式完整数据备份和恢复
- **数据安全**：本地 SQLite 存储，无云端依赖
- **设置管理**：可配置版本清理阈值等系统参数

## 🚀 快速开始

### 方式一：Docker 运行 (推荐)

#### 环境要求
- Docker 和 Docker Compose

#### 使用 Docker Compose

1. **克隆项目**
   ```bash
   git clone https://github.com/zhuchenyu2008/prompt-manage
   cd prompt
   ```

2. **启动应用**
   ```bash
   # 启动服务
   docker-compose up
   # 或后台运行
   docker-compose up -d
   ```
   访问：http://localhost:3501

#### 使用单独的 Docker

```bash
# 构建镜像
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

> **注意**：首次运行会自动创建 `data.sqlite3` 数据库文件，无需手动配置。

## 📁 项目结构

```
prompt/
├── app.py              # Flask 应用主文件
├── requirements.txt    # Python 依赖文件
├── data.sqlite3        # SQLite 数据库文件(自动创建)
├── Dockerfile          # Docker 镜像配置
├── docker-compose.yml  # Docker Compose 配置文件
├── .dockerignore       # Docker 构建忽略文件
├── templates/          # HTML 模板
│   ├── layout.html     # 基础布局模板
│   ├── index.html      # 首页(列表视图)
│   ├── prompt_detail.html # 详情页(编辑页面)
│   ├── versions.html   # 版本历史页面
│   ├── diff.html       # 对比页面
│   └── settings.html   # 设置页面
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
  - `id`, `name`, `source`, `notes`, `tags`, `pinned`, `created_at`, `updated_at`, `current_version_id`
- **versions**: 版本历史记录
  - `id`, `prompt_id`, `version`, `content`, `created_at`, `parent_version_id`
- **settings**: 系统设置
  - `key`, `value` (目前仅 `version_cleanup_threshold`)

### 数据导出示例

```json
{
  "prompts": [
    {
      "id": 1,
      "name": "客服助手",
      "source": "ChatGPT",
      "notes": "处理客户咨询的标准回复模板",
      "tags": ["场景/客服", "业务/售后"],
      "pinned": true,
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
4. **数据库损坏**：删除 `data.sqlite3` 重新生成

### 重置系统
如需重置所有数据，删除 `data.sqlite3` 文件后重启应用即可。

## 📝 更新日志

### 最新功能
- ✅ 完善的黑夜模式适配
- ✅ 首页内容预览一键复制
- ✅ 动态页面标题显示
- ✅ 简化的用户界面
- ✅ 增强的颜色主题系统

