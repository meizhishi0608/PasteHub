# PasteHub 剪贴板记录

一个简单、轻量、完全离线的 Windows 剪贴板记录工具。

> 自动记录每天复制过的文字和截图，按日期回看，一键重新复制。

## 功能
- **自动记录**：后台运行，持续记录剪贴板里的文字和截图（图片）
- **按日期回看**：日历视图可翻到任意年月（2026 – 2099），点选某一天查看当天内容
- **一键重新复制**：看到想要的记录，双击列表项，或选中后点「复制这条」，或按 Ctrl+C / Enter
- **搜索**：按关键词搜索所有历史记录
- **图片缩略图**：图片自动生成缩略图，加载快；原图完整保存
- **完全离线**：数据只保存在你自己的电脑上，不上传任何内容

## 运行环境
- Windows 10 / 11（仅支持 Windows）
- Python 3.10 或更高版本
- 首次启动需要联网，自动安装 Pillow（图片处理库，只需一次）

不需要安装 PyCharm、VSCode、Git 等任何编程工具。

## 下载与安装

### 1. 在D盘创建指定文件夹
- 1. 创建主目录
md D:\PasteHub
cd /d D:\PasteHub

- 2. 创建data文件夹
md data

- 3. 生成配置文件
copy config.example.json config.json


### 2. 把代码放进 D 盘

拉取代码
git clone https://github.com/meizhishi0608/PasteHub.git .

最终目录结构：

```
D:\PasteHub
├─ data                  # 剪贴记录数据存放目录
│  ├─ text
│  ├─ images
│  ├─ thumbs
│  └─ index
├─ 启动.bat              ← 双击它启动
├─ clipboard_monitor.pyw
├─ app.ico
├─ requirements.txt
├─ config.example.json
├─ config.json
└─ README.md

```

### 3. 启动
双击 `启动.bat`。第一次会自动完成四件事：
1. 检测 Python
2. 安装 Pillow（图片处理库）
3. 启动程序，并自动创建 `data` 数据文件夹
4. 在桌面自动创建 `PasteHub` 快捷方式（如果还没有的话）

之后程序在后台运行，开始记录。**不需要手动创建任何文件夹。** 以后每天使用，直接双击桌面的 `PasteHub` 快捷方式即可。

## 使用说明
- **打开窗口**：双击桌面的 `PasteHub` 快捷方式（或再双击一次 `启动.bat`），如果程序已在运行，会自动把窗口调到前台
- **查看某天**：用日历选择日期，下方列出当天的记录
- **重新复制**：双击某条记录；或选中后点右上角「复制这条」；列表聚焦时按 Ctrl+C / Enter 也可以
- **搜索**：顶部搜索框输入关键词，回车搜索全部历史
- **暂停 / 继续**：窗口右上角「暂停记录」可临时停止记录（复制密码等敏感内容时建议使用）
- **数据文件夹**：窗口右上角「打开数据文件夹」可直接打开

## 数据与隐私
- 所有数据保存在程序所在目录的 `data` 文件夹，完全本地，**不会上传到任何地方**
- `data` 文件夹结构：

```
data
├── text\    当天复制的所有文字（按日期归档）
├── images\  当天复制的截图原图
├── thumbs\  缩略图（浏览更快）
└── index\   每天的记录索引
```

- 注意：剪贴板里可能出现密码、验证码等敏感内容，建议复制敏感内容时先点「暂停记录」；不要把 `data` 文件夹发给别人，也不要上传到 GitHub

## 配置文件（可选）
默认不需要任何配置。如果想自定义，把 `config.example.json` 复制一份并改名为 `config.json` 即可：

```json
{
  "data_dir": "data",
  "poll_interval_ms": 700,
  "max_text_len": 200000,
  "save_images": true
}
```

- `data_dir`：数据保存位置（相对路径表示放在程序目录下）
- `poll_interval_ms`：检测剪贴板的间隔（毫秒），越小越及时、略耗电
- `max_text_len`：单条文本最多保存的字符数
- `save_images`：是否记录图片

注意：`config.json` 和 `data/` 已在 `.gitignore` 中，上传到 GitHub 时不会包含你的个人记录。

## 开机自启（可选）
想让电脑一开机就自动开始记录：

1. 先正常双击一次 `启动.bat`（此时桌面上已经自动生成了 `PasteHub` 快捷方式）
2. 按 `Win + R`，输入 `shell:startup`，回车，打开开机启动文件夹
3. 把桌面的 `PasteHub` 快捷方式复制粘贴进去即可

这个快捷方式直接指向程序，开机启动时不会弹出黑色窗口。

## 常见问题
- **双击启动.bat 一闪而过 / 提示没有 Python**：先按上面第 1 步安装 Python，勾选 Add Python to PATH，装好后再双击
- **提示 Pillow 安装失败**：检查网络后重新双击 `启动.bat` 即可
- **启动后没看到窗口**：程序默认在后台运行；双击桌面 `PasteHub` 快捷方式（或再双击一次 `启动.bat`）会把窗口调出来
- **桌面上没有 PasteHub 快捷方式**：再双击一次 `启动.bat`，它会自动补建
- **杀毒软件拦截**：程序是本地脚本，不会上传任何数据；如有提示，选择「允许」

## 本仓库内容
| 文件 | 说明 |
| --- | --- |
| `clipboard_monitor.pyw` | 主程序（全部代码就这一个文件） |
| `启动.bat` | 一键启动脚本：检测 Python、安装 Pillow、创建桌面快捷方式、启动程序 |
| `app.ico` | 应用图标 |
| `requirements.txt` | Python 依赖清单（Pillow） |
| `config.example.json` | 配置示例 |
| `.gitignore` | 上传 GitHub 时自动忽略 `data/`、`config.json` 等 |

## 开源说明
本项目暂未指定开源许可证。如果你打算公开分享，建议在仓库里补充一个 LICENSE 文件（例如 MIT）。
