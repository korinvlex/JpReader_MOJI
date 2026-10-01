# ✨ JpReader AI（中文版）

> 一个美观、专注「通过阅读学日语」的桌面阅读器。
> 本项目基于 [C-YuLong/JpReader](https://github.com/C-YuLong/JpReader) 二次开发，新增了 **MOJi辞書 云查词 / 生词本** 能力。

**核心工作流：**

> **阅读 → 高亮 → 问 AI → 查词 → 存生词 → 导出复习**

---

## 目录

- [今天新增了什么](#new-today)
- [功能特性](#features)
- [技术栈](#tech)
- [项目结构](#structure)
- [安装运行](#install)
- [打包 EXE](#build)
- [AI 配置](#ai-config)
- [MOJi 词典说明](#moji)
- [隐私与数据](#privacy)
- [致谢](#credits)

---

<a id="new-today"></a>

## 🆕 今天新增了什么（相对原版）

在原版（阅读 + 高亮 + AI 语法分析）的基础上，集成了 **MOJi辞書（mojidict.com）** 的查词能力，对齐 MOJi 浏览器插件「划词即查」的体验，但不需要浏览器：

| 能力 | 说明 |
| --- | --- |
| 📖 **词典 Tab** | 输入或划选日语 → 云端查词 → 词条详情（释义、音调 ⓪①②、词性、日文释义、例句） |
| 🖱 **划词查词** | 阅读时选中文本 → 浮动工具条点「查词」→ 自动跳转到词典页查询 |
| 📚 **生词本 Tab** | 一键收藏词条，带完整释义与例句；支持删除与导出 Markdown |
| 🔗 **在线词典直达** | Weblio / Jisho / Kotobank / Google 翻译一键跳转，无需登录 |
| 🔑 **MOJi 账号登录（可选）** | 未登录也可查词；在「文件 → 设置」登录 MOJi 账号可解锁更高查词额度，本地仅保存登录 token |
| 🌐 **OPDS 在线书库** | 浏览任意 OPDS 书库（Anna's Archive、Gutenberg、Feedbooks 等），分类导航 → 下载 → 直接阅读 |

> 技术说明：直接调用 mojidict.com 的官方 REST 接口（`/api/v2/search/all` 搜索 + `/api/v1/word/detailInfo` 详情），支持假名 / 日文 / 中文 / 罗马音自动识别；未登录即可查词，登录只用于提高额度。

---

<a id="features"></a>

## ⚡ 功能特性

### 📚 电子书阅读
- 支持 **EPUB / MOBI / AZW / AZW3**
- Windows 清爽桌面阅读体验
- 自动恢复上次阅读位置
- 长书的章节导航
- 自动分页、字体缩放（高亮 / 笔记 / 查词 / 解析 浮动工具条）

### 🖍 高亮与批注
- 选中任意句子或段落添加高亮，长期保存
- 阅读笔记与指定书籍、章节关联
- 集中回顾所有高亮

### 🧠 AI 语法分析
- 将选中的日文句子发送给 AI 模型，返回：
  - 句子拆解、语法讲解
  - 单词层级释义、假名/读音提示
  - 完整翻译、学习建议
- 兼容 OpenAI 接口（OpenAI / DeepSeek / Moonshot / 本地 Ollama 等）

### 📖 MOJi 词典查词（新增）
- 划词查词、云查词、词条详情、生词本、在线词典直达（详见上文）

### 🌐 OPDS 在线书库（新增）
- 「在线书库」页签：输入书库地址即可浏览（兼容 OPDS 1.x / 2.x 目录格式）
- 目录层级导航（返回 / 首页 / 上一页 / 下一页 / 面包屑）
- 书籍详情（作者、简介、更新时间）、一键「下载」或「下载并阅读」
- 已下载的书自动保存到下载目录，epub/mobi/azw/azw3 可直接在阅读器中打开
- ☆ 收藏常用书库地址，下次启动自动打开第一个收藏的书库
- 🔑 **支持需要登录的书库**（见下节）
- 下载目录可在「文件 → 设置 → OPDS 在线书库」自定义（默认 `数据目录/opds_downloads`）

#### 🔑 登录受保护的 OPDS 书库

很多自建 / 商业书库需要认证。客户端支持四种方式，**遇到 401 会自动弹窗让你填写，成功后自动重试**，无需手动排查：

| 认证方式 | 适用场景 | 需要填写 |
| --- | --- | --- |
| **HTTP Basic** | Calibre-Web、COPS、Kavita、Komga、Ubooquity 等绝大多数自建服务 | 用户名 + 密码 |
| **HTTP Digest** | 少数自建服务 / 老式 Apache 配置 | 用户名 + 密码 |
| **Bearer 令牌** | 提供 OAuth 2.0 的商业书库 | 访问令牌 |
| **自定义请求头** | 用 `X-Api-Key` 之类的私有服务 | 请求头名 + 值 |

使用流程：

1. 输入书库地址并「打开书库」
2. 若返回 401，**自动弹出登录框**（已根据服务器声明的认证方式预选好类型）
3. 填写凭据 → 「保存并连接」，自动用新凭据重试
4. 凭据会与该书库地址绑定保存，**浏览和下载共用**，下次打开无需重填

也可以随时点「🔑 登录」手动配置或更换认证方式。

> **关于凭据安全**：用户名以明文保存，密码 / 令牌 / 请求头值做了本地混淆（Base64 + 密钥异或）后存入 `config.json`，避免明文肉眼可见。**这不是加密**——能读取你本机文件的程序仍可还原它。请勿在共享电脑上保存重要凭据。

> 试试这些公开书库：`https://wolnelektury.pl/opds/`（波兰公版书，无需登录）。私有书库请填写你自己的服务地址。

### 📝 笔记系统
- **学习笔记**：语法 / 词汇 / 可复用语言笔记
- **阅读笔记**：与特定书籍和章节绑定
- 导出笔记用于复习或外部整理

### 📤 导出支持
- 高亮：Markdown / JSON / Anki TSV
- 笔记：Markdown
- 生词本：Markdown
- 全部数据：ZIP 归档

### ⚙ 设置与用量统计
- 配置 API Base URL / API Key / 模型名 / JLPT 等级
- 统计请求数、输入输出 token、总 token 用量

---

<a id="tech"></a>

## 🧩 技术栈

- **Python**
- **PyQt5** —— 桌面 UI
- **ebooklib** —— EPUB 解析
- **BeautifulSoup4** —— HTML 内容提取
- **mobi** —— MOBI 提取 / 转换
- **SQLite** —— 本地存储进度、笔记、高亮、生词本
- **requests** —— AI 接口与 MOJi 云查词请求
- **PyInstaller** —— 打包为 `.exe`

---

<a id="structure"></a>

## 📂 项目结构

```bash
reader/
├── main.py               # 入口与主窗口
├── reader_core.py        # 阅读核心 / 分页 / 高亮
├── ai_client.py          # AI 语法分析客户端
├── moji_dict.py          # MOJi辞書 查词/登录封装（新增）
├── dictionary_panel.py   # 词典页 + 生词本页（新增）
├── storage.py            # SQLite 存储（含生词本表、OPDS 配置）
├── settings_dialog.py    # 设置（含 OPDS 下载目录）
├── opds_client.py        # OPDS 1.x/2.x 目录解析、认证与下载（新增）
├── opds_panel.py         # 「在线书库」页签（新增）
├── opds_auth_dialog.py   # 书库登录对话框（新增）
├── build.bat             # 一键打包脚本（新增）
├── notes_panel.py        # 笔记面板
├── floating_bar.py       # 浮动工具条（含「查词」）
├── ui_style.py           # 界面样式
├── assets/
│   └── icon.ico
└── requirements.txt
```

---

<a id="install"></a>

## 🛠 安装运行

```bash
# 1. 克隆
git clone https://github.com/korinvlex/JpReader_MOJI.git
cd JpReader_MOJI

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

---

<a id="build"></a>

## 📦 打包 Windows EXE

> ⚠️ **请使用 Python 3.11 / 3.12 打包**。`mobi` 库依赖 `imghdr`，而该标准库在 Python 3.13 中已被移除，用 3.13+ 打包出的程序无法导入 `mobi`。

**方式一：一键脚本（推荐）**

```bash
build.bat
```

**方式二：手动命令**

```bash
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --name JpReader ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --collect-all ebooklib ^
  --collect-all mobi ^
  main.py
```

生成的可执行文件在 `dist/JpReader.exe`（约 46 MB，首次启动需解包，稍慢）。

---

<a id="ai-config"></a>

## 🤖 AI 配置

在「文件 → 设置」中填写：

- `base_url` —— API 基地址
- `api_key` —— API 密钥
- `model` —— 模型名
- JLPT 等级 —— 让分析贴合当前水平

系统提示词会附带当前 JLPT 等级、书名与选中的日文句子，让 AI 解释更有上下文。

---

<a id="moji"></a>

## 📖 MOJi 词典说明

- **查词无需登录**：直接调用 mojidict.com 官方接口，假名 / 中文 / 英文 / 罗马音自动识别。
- **登录（可选）**：在「文件 → 设置 → MOJi 词典账号」登录 MOJi 账号（使用 MOJi 辞書 App 或官网账号），可获得更高查词额度。本地**只保存登录 token**，不会保存密码。
- **词条详情**：音标、音调、词性、中日释义、例句，均可直接收藏进生词本。
- **生词本**：带来源（原文句子 + 书名），支持删除与导出 Markdown，方便后续复习或导入 Anki。

---

<a id="privacy"></a>

## 🔐 隐私与数据

所有数据保存在本地 SQLite 中：

- 阅读进度、高亮、笔记
- 生词本
- 使用配置（不含 MOJi 密码）

数据目录：`%APPDATA%\JpReader\`

---

<a id="credits"></a>

## 🙏 致谢

- 原项目：[C-YuLong/JpReader](https://github.com/C-YuLong/JpReader) —— 阅读、高亮、AI 语法分析基础框架
- 词典能力：[MOJi辞書](https://mojidict.com) —— 查词与词条数据

如果你觉得好用，欢迎点个 ⭐
