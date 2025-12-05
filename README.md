# PPT Helper - 智能课件讲解助手

基于 Gemini Vision 的 PDF 课件智能解析系统，将复杂的学术内容转化为通俗易懂的中文解释。

## 🎯 核心功能

- **图像理解**: 使用 PyMuPDF 将 PDF 转为高清图像，通过 Gemini Vision 分析
- **智能解释**: AI 自动识别 PPT 中的文字、图表、公式，生成中文讲解
- **分屏查看**: 左侧原始 PDF，右侧 AI 解释，实时同步
- **按页缓存**: 前端状态管理，翻页流畅不丢失内容

## 🚀 快速开始

### 环境要求

- Python 3.11+ (推荐使用 conda)
- Node.js 18+
- Google Gemini API Key ([免费获取](https://aistudio.google.com/apikey))

### 一、后端安装

```bash
# 1. 创建 conda 环境
conda create -n ppt_helper python=3.11
conda activate ppt_helper

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 GOOGLE_API_KEY
```

### 二、前端安装

```bash
cd frontend
npm install
```

### 三、启动服务

**方式1: 使用启动脚本（推荐）**

```bash
# Windows - 根目录运行
start_all.bat

# Linux/Mac - 根目录运行
chmod +x start_all.sh
./start_all.sh
```

**方式2: 手动启动**

```bash
# 终端1 - 启动后端
conda activate ppt_helper
cd backend
python -m uvicorn app.main:app --reload

# 终端2 - 启动前端
cd frontend
npm run dev
```

### 四、使用

1. 打开浏览器访问: `http://localhost:3000`
2. 上传 PDF 课件
3. 左侧查看原始 PDF，右侧查看 AI 解释
4. 点击翻页按钮或使用快捷键浏览

## 📦 技术栈

### 后端
- **框架**: FastAPI
- **PDF处理**: PyMuPDF (fitz) - 高质量图像渲染
- **AI模型**: Google Gemini 2.5 Flash (Vision)
- **数据库**: SQLite (开发环境)
- **缓存**: 禁用（便于调试，生产环境可启用）

### 前端
- **框架**: Next.js 14 (App Router)
- **PDF查看**: react-pdf
- **状态管理**: Zustand (按页面跟踪加载状态)
- **样式**: Tailwind CSS (简洁黑白风格)

## 🏗️ 项目结构

```
ppt_helper/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 主路由
│   │   ├── config.py            # 配置管理
│   │   ├── models/
│   │   │   ├── database.py      # 数据库模型
│   │   │   └── schemas.py       # API 数据结构
│   │   └── services/
│   │       ├── pdf_parser.py    # PDF -> 图像
│   │       ├── cache_service.py # 缓存服务
│   │       └── llm_service.py   # Gemini Vision
│   ├── uploads/                 # PDF 存储
│   ├── data/                    # SQLite 数据库
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # 主页面
│   │   └── layout.tsx          # 布局
│   ├── components/
│   │   ├── PdfUpload.tsx       # PDF 上传
│   │   ├── PdfViewer.tsx       # PDF 显示
│   │   └── ExplanationPanel.tsx # 解释面板
│   ├── store/
│   │   └── pdfStore.ts         # 状态管理
│   ├── lib/
│   │   └── api.ts              # API 调用
│   └── package.json
│
├── start_all.bat               # Windows 启动脚本
├── start_all.sh                # Linux/Mac 启动脚本
└── README.md
```

## 🔧 核心实现

### 1. PDF 图像提取

使用 PyMuPDF 将 PDF 页面渲染为 150 DPI 图像，确保文字、图表、公式清晰可见：

```python
# backend/app/services/pdf_parser.py
import fitz  # PyMuPDF
from PIL import Image

def extract_page_as_image(pdf_path, page_num):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    zoom = 150 / 72  # 150 DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png")))
```

### 2. Gemini Vision 分析

将图像发送给 Gemini 2.5 Flash，自动识别并解释内容：

```python
# backend/app/services/llm_service.py
async def analyze_image(image, prompt):
    response = model.generate_content(
        [prompt, image],
        safety_settings=[{"category": cat, "threshold": "BLOCK_NONE"}]
    )
    return response.text
```

### 3. 按页状态管理

前端使用 Zustand + Set/Map 实现按页面独立跟踪加载状态：

```typescript
// frontend/store/pdfStore.ts
interface PdfState {
  explanations: Map<number, PageExplanation>;  // 缓存解释
  loadingPages: Set<number>;                   // 加载中的页面
  pageErrors: Map<number, string>;             // 各页面错误
}
```

### 4. JSON 修复机制

处理 Gemini 输出被截断的情况，自动补全括号：

```python
# backend/app/main.py
if response_text.count('"') % 2 != 0:
    response_text += '"'
response_text += "}" * (response_text.count("{") - response_text.count("}"))
response_text += "]" * (response_text.count("[") - response_text.count("]"))
```

## 🔍 API 接口

### 上传 PDF
```bash
POST /api/upload
Content-Type: multipart/form-data

Response:
{
  "pdf_id": "947eef32ae452ad2",
  "total_pages": 12,
  "filename": "lecture.pdf"
}
```

### 获取页面解释
```bash
GET /api/explain/{pdf_id}/{page_number}

Response:
{
  "page_number": 1,
  "page_type": "CONTENT",
  "content": {
    "summary": "页面摘要",
    "key_points": [
      {
        "concept": "核心概念",
        "explanation": "通俗解释",
        "is_important": true
      }
    ],
    "analogy": "生活类比",
    "example": "具体例子"
  },
  "original_language": "en"
}
```

## 🐛 版本历史与Bug修复

### v0.3.0 (2025-12-05)

**重大更新**:
- ✅ 改用 PyMuPDF 图像提取 + Gemini Vision (替代纯文本)
- ✅ 完全禁用安全过滤器，学术内容不再被误判
- ✅ 前端按页面跟踪状态，翻页不丢失已加载内容
- ✅ JSON 自动修复机制，处理输出截断问题
- ✅ 增加 max_tokens 到 4000，简化 prompt 减少消耗
- ✅ 禁用缓存（开发环境），便于调试

**Bug修复**:
- 🐛 修复 Gemini finish_reason=2 安全阻止问题
- 🐛 修复 PPT 图表、公式无法识别的问题
- 🐛 修复前端翻页时 isLoadingExplanation 全局状态导致已加载内容消失
- 🐛 修复 JSON 被截断导致解析失败（Unterminated string）

### v0.2.0 (2025-12-04)

**新功能**:
- ✅ 前端黑白简洁设计
- ✅ 左右分屏布局
- ✅ react-pdf 集成
- ✅ Zustand 状态管理

### v0.1.0 (2025-12-03)

**初始版本**:
- ✅ FastAPI 后端
- ✅ 仅支持 Gemini API
- ✅ PyPDF2 文本提取
- ✅ SQLite 缓存

## ⚙️ 配置说明

### 环境变量 (.env)

```env
# Google Gemini API Key (必需)
GOOGLE_API_KEY=your-api-key-here

# Gemini 模型配置
GOOGLE_MODEL=gemini-2.5-flash
TEMPERATURE=0.7
MAX_TOKENS=4000

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

### 性能调优

**DPI 设置**: 默认 150，可在 `backend/app/services/pdf_parser.py` 调整
- 更低 DPI (100): 更快，文件小，适合文字为主的 PPT
- 更高 DPI (200): 更清晰，适合含大量图表的 PPT

**Token 限制**: 默认 4000，可在 `backend/app/main.py` 调整
- 简单页面: 2000 足够
- 复杂页面: 4000-8000

## 🔍 故障排除

### 后端报错: "GOOGLE_API_KEY 未配置"
**解决**: 检查 `.env` 文件是否存在，且包含有效的 API Key

### 前端显示 "加载失败"
**解决**:
1. 查看浏览器控制台错误
2. 检查后端是否运行 (`http://localhost:8000/docs`)
3. 查看后端终端日志

### PDF 上传后无响应
**解决**:
1. 检查 PDF 文件大小 (< 50MB)
2. 确认 PDF 无密码保护
3. 查看后端日志是否有 PyMuPDF 错误

### Gemini 返回 "此页面内容因安全原因无法生成解释"
**解决**:
- 该问题已在 v0.3.0 修复
- 如仍出现，检查 `llm_service.py` 的 safety_settings 配置

### JSON 解析失败
**解决**:
- v0.3.0 已添加自动修复机制
- 如频繁出现，尝试增加 max_tokens 或简化 prompt

## 💰 成本估算

**使用 Gemini 2.5 Flash**:
- PDF 解析: 本地 PyMuPDF (免费)
- AI 分析: Gemini 2.5 Flash 测试期免费
- **总成本**: $0/月 (测试期)

**生产环境** (Gemini API 收费后):
- 假设: 10 个用户 × 5 份 PDF × 50 页 = 2500 页/月
- 成本: ~$5-10/月 (根据 Gemini 定价)

## 🧹 项目清理

### 清理空目录和缓存

项目包含一些空目录和临时文件，可以安全删除：

```bash
# Windows
cleanup.bat

# Linux/Mac
chmod +x cleanup.sh
./cleanup.sh
```

清理内容：
- ✅ 删除空目录（`backend/app/agents`, `backend/examples`）
- ✅ 清理临时 PDF 文件
- ✅ 删除 Python 缓存（`__pycache__`）
- ⚠️ 可选：清理数据库缓存（会提示确认）

详细说明见 [CLEANUP_GUIDE.md](CLEANUP_GUIDE.md)

## 🤝 贡献与支持

这是一个个人学习项目，欢迎提出建议和问题！

## 📄 许可

仅供个人学习使用。

---

**使用 Claude Code 构建** 🤖
