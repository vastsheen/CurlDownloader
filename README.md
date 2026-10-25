# CurlDownloader 资源下载器

一个 Windows 图形化下载工具：把从浏览器复制出来的 cURL 命令、HAR 抓包、磁力链接和 `.torrent` 文件，统一转换成 `yt-dlp` / `aria2c` 任务下载到你指定的目录，并提供进度条与日志。

程序本身不实现 HTTP 传输，只负责解析参数、拼装命令行、读取子进程进度。

---

## 功能

- **cURL 解析**：支持 Windows `cmd` 式的 `curl.exe "..." -H "..."`（含反斜杠换行、引号转义），提取 URL、Referer、Origin、Cookie、User-Agent。
- **粘贴即下载**：保存目录常驻在窗口顶部；把 cURL / 链接 / 磁力粘进输入框后直接按该目录开始下载，不再需要额外点按钮。
- **批量下载**：一次粘贴多段 cURL 或一行一个 URL，按顺序下载，文件名自动编号（见「批量命名规则」）。
- **磁力 / 种子**：走内置的 `aria2c`，开启 DHT、DHT6、PEX、LPD 与内置 tracker 列表。
- **HAR 抓包**：
  - 优先识别成功的 `.m3u8` / `#EXTM3U` 播放列表请求；
  - 否则按 `Content-Range` 归组 MP4 分片，音视频分离时交给 `yt-dlp` 拉完整资源、`ffmpeg` 合并；
  - 解析完成后先弹出确认框，列出所有待下载链接，点「确定」才开始下载，点「取消」什么都不做。
- **断点续传**：同目录同文件名失败后可续传（`--continue`，保留 `.part` / `.ytdl`）。
- **进度与日志**：解析 `yt-dlp` / `aria2c` 输出实时更新进度条，日志在窗口内滚动显示。

---

## 目录结构

```
CurlDownloader/
├─ main.py                     # 程序入口（PyInstaller 也从这里打包）
├─ curldownloader/             # 主程序包
│  ├─ __init__.py              # 版本号
│  ├─ app.py                   # Tkinter 界面、事件与任务调度
│  ├─ paths.py                 # 资源路径解析（源码运行 / 打包运行）
│  ├─ curl_parser.py           # cURL 解析与请求模型
│  ├─ har_parser.py            # HAR 播放列表与分片媒体提取
│  ├─ downloader.py            # yt-dlp 命令构建、编号、执行
│  ├─ bt_downloader.py         # aria2c 磁力 / 种子下载
│  ├─ progress_parser.py       # 进度行解析
│  └─ progress_ui.py           # 进度面板与主题
├─ tests/                      # 单元测试（pytest）
├─ bin/                        # 外部二进制：yt-dlp、ffmpeg、aria2c
├─ .gitattributes              # Git LFS 规则（bin/ffmpeg.exe）
├─ build.ps1                   # 构建主逻辑（PowerShell）
├─ build.bat                   # 双击入口：自动绕过执行策略，必要时退回纯 cmd 构建
├─ run.bat                     # 源码方式启动
├─ requirements.txt            # 构建依赖（PyInstaller）
├─ requirements-dev.txt        # 测试依赖（pytest）
└─ README.md
```

---

## 依赖

### 1. 构建与运行环境

| 项目 | 要求 | 本机实测 |
|---|---|---|
| 操作系统 | Windows 10 / 11（x64） | Windows 11 10.0.26300 |
| Python | 3.10 及以上 | 3.14.8 |
| PyInstaller | 6.x | 6.22.3 |
| PowerShell | 5.1 或 7.x（`build.ps1` 使用） | 7.x |

Python 包依赖统一在 `requirements.txt`：

```
pyinstaller>=6.0
```

测试依赖在 `requirements-dev.txt`：

```
pytest>=8.0
```

### 2. 外部二进制（`bin/` 目录）

这三个不是 pip 包，是需要随程序分发的可执行文件。

| 文件 | 版本 | 大小 | 是否入库 | 稳定下载地址 |
|---|---|---|---|---|
| `bin/yt-dlp.exe` | 2026.03.17 | 17.59 MB | **是（Git LFS）** | <https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe> |
| `bin/aria2c.exe` | aria2 1.37.0 | 5.39 MB | **是（Git LFS）** | <https://github.com/aria2/aria2/releases/tag/release-1.37.0>（下载 `aria2-1.37.0-win-64bit-build1.zip`，解压取 `aria2c.exe`） |
| `bin/ffmpeg.exe` | git-2020-07-16-d11cc74（GPL 构建） | 65.52 MB | **是（Git LFS）** | <https://www.gyan.dev/ffmpeg/builds/>（下载 essentials 构建，解压取 `ffmpeg.exe`） |

校验（SHA-256，对应上面这三个文件）：

```
aria2c.exe  BE2099C214F63A3CB4954B09A0BECD6E2E34660B886D4C898D260FEBFE9D70C2
ffmpeg.exe  51D2640F162503EBAD6719B40CA3FB34CD09BE50B5EA4945D82EDFF6FE26EAD8
yt-dlp.exe  3DB811B366B2DA47337D2FCFDFE5BBD9A258DAD3F350C54974F005DF115A1545
```

> 三个二进制都是**默认依赖**，随仓库提供（由 Git LFS 存储），`git clone` 后离线即可构建，不需要任何下载步骤。`yt-dlp` 仅在文件被删除时，构建脚本才会尝试联网补一份。
>
> `bin/ffmpeg.exe` 是 2020 年的老 GPL 构建，只适合本地合并测试。若要对外分发，请换成当前 gyan.dev essentials 版本，并自行确认 GPL 的分发义务。

### 3. 获取代码（Git LFS）

`bin/` 下的三个二进制合计约 88.5 MB，全部由 **Git LFS** 管理。克隆前确认本机装了 git-lfs（Git for Windows 自带）：

```powershell
git lfs version                       # 应输出 git-lfs/3.x
git lfs install                       # 每台机器只需一次
git clone https://github.com/vastsheen/CurlDownloader.git
cd CurlDownloader
git lfs pull                          # 克隆时没自动拉取大文件的话补一步
```

克隆完检查三个文件都是真实二进制，而不是一百多字节的指针文本：

```powershell
Get-ChildItem bin\*.exe | Select-Object Name, Length
# yt-dlp.exe   18448981
# ffmpeg.exe   68700672
# aria2c.exe    5649408

Get-FileHash bin\*.exe -Algorithm SHA256
# 与上一节的校验值逐一对上
```

没装 git-lfs 时克隆下来的只是 LFS 指针：`ffmpeg` 会让 HAR 音视频合并失败，`aria2c` 会让 BT 下载报「未找到 aria2c.exe」，`yt-dlp` 则所有 HTTP 下载都起不来。

---

## 构建（重点）

### 1. 前置检查

```powershell
python --version          # 需要 3.10+，没有的话先装 Python 并勾选 Add to PATH
git --version             # 可选，仅用于拉取仓库
```

确认 `bin\` 下 `yt-dlp.exe`、`ffmpeg.exe`、`aria2c.exe` 三个文件都在（仓库里已带）。若缺失，先执行 `git lfs pull`；确实拉不下来时按上一节的地址手动补齐，否则构建脚本会直接报错退出。

### 2. 一键构建

#### 方式 A：build.bat（推荐）

双击 `build.bat`，或在终端里执行：

```bat
cd /d D:\Tools\CurlDownloader
build.bat
```

它分两步：

1. 先用 `pwsh -NoProfile -ExecutionPolicy Bypass -File build.ps1` 跑主逻辑（`-ExecutionPolicy Bypass` 只对本次进程生效，不改系统设置）；
2. 如果 PowerShell 不存在、`.ps1` 被执行策略禁止、或被组策略拦截而失败，**自动退回纯 cmd 构建**：直接调用 `pip`、`PyInstaller`、`copy`、`xcopy`，不执行任何脚本文件，产物与方式 B 完全一致。

所以「这台机器不让跑 ps1」不会卡住构建，最差也是多花一次重试的时间。

#### 方式 B：直接运行 build.ps1

```powershell
cd D:\Tools\CurlDownloader
Set-ExecutionPolicy -Scope Process Bypass
.\build.ps1
```

如果仍然报「无法加载文件 … 因为在此系统上禁止运行脚本」，改用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

若提示 *此系统上禁止运行脚本* 且加了参数也不行（通常是组策略强制 `MachinePolicy`），说明本机彻底不允许脚本执行，请改用方式 A 或方式 C。

`build.ps1` 依次做这些事：

1. 定位脚本所在目录，`bin\` 不存在就创建；
2. 检查 `bin\` 下三个二进制；只有 `yt-dlp.exe` 缺失时才会联网下载一份兜底，正常克隆不会触发；
3. 三个文件不齐则直接抛错，并提示对应的下载地址；
4. `python -m pip install -r requirements.txt` 安装 PyInstaller；
5. 以 **onedir** 模式打包：`--windowed --name CurlDownloader --paths .`，并把三个二进制通过 `--add-data` 塞进包内的 `bin\`；
6. 把 `dist\CurlDownloader\CurlDownloader.exe` 复制到项目根目录，同时把 `_internal\` 整个复制到根目录；
7. 打印最终路径。

### 3. 构建产物

```
CurlDownloader.exe     ← 双击启动
_internal\             ← 运行时依赖，必须和 exe 放在同一目录
└─ bin\                 ← 打包进去的 yt-dlp / ffmpeg / aria2c
```

**这是 onedir 模式，exe 不能单独拷走。** 分发时把 `CurlDownloader.exe` 和 `_internal\` 打成一个压缩包一起发。

构建过程中还会生成 `build\` 和 `dist\`，它们是中间目录，可以随时删除（`.gitignore` 已忽略）。

### 4. 方式 C：完全手动（不走任何脚本）

上面的命令就是 `build.bat` 回退阶段在做的事。在终端里逐条粘贴即可，适合脚本执行被彻底禁止、或想自定义打包参数的场景。`ffmpeg.exe` / `aria2c.exe` 的存在性需要你自己确认。

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed `
    --name "CurlDownloader" --paths "." `
    --add-data "bin/yt-dlp.exe;bin" `
    --add-data "bin/ffmpeg.exe;bin" `
    --add-data "bin/aria2c.exe;bin" `
    main.py
Copy-Item "dist\CurlDownloader\CurlDownloader.exe" . -Force
Copy-Item "dist\CurlDownloader\_internal" . -Recurse -Force
```

### 5. 常见构建问题

| 现象 | 原因与处理 |
|---|---|
| `无法加载文件 …\build.ps1，因为在此系统上禁止运行脚本` | 执行策略禁止运行 `.ps1`。改用 `build.bat`（自动带 `-ExecutionPolicy Bypass`，仍被禁止时退回 cmd 构建），或执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1`。 |
| `build.bat` 打印 `[WARN] ... Falling back to a direct build` | 正常现象：PowerShell 侧没跑通，正在用 cmd 直接构建，产物一致，无需处理。 |
| `Warning: failed to copy _internal...`，退出码 1 | 上次的 `CurlDownloader.exe` 还在运行，占用了 `_internal`。关掉窗口后重跑。 |
| `bin\*.exe` 只有一百多字节 | 克隆时没启用 Git LFS，拿到的是指针文件。执行 `git lfs install` + `git lfs pull` 还原三个二进制，确认大小（68700672 / 18448981 / 5649408）后重新构建。 |
| `Missing ...\bin\ffmpeg.exe` | `bin\` 里的二进制没跟着仓库下来，按上一节地址下载补齐。 |
| `'python' 不是内部或外部命令` | Python 没加进 PATH，重装时勾选 *Add Python to PATH*，或用绝对路径调用。 |
| 双击 exe 闪退 | 只拷了 exe、没带 `_internal`；或 `_internal` 与 exe 版本不匹配。整包重发。 |
| 杀毒软件报毒 | PyInstaller 打包的程序常被误判为可疑，加信任即可；也可改用源码运行。 |
| 想清理中间产物 | 删 `build\`、`dist\`、`__pycache__\` 即可，不影响已构建的 exe。 |

---

## 源码运行

```powershell
.\run.bat
# 或
python main.py
```

需要本地有 Python 3.10+；`bin\` 下的二进制按相对路径查找，缺失时会在日志里给出警告（BT 功能还会直接报错）。

---

## 测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

覆盖点：cURL 解析（含多条 cURL、纯 URL 列表）、重名处理、断点续传命名、批次编号补零、HAR m3u8 提取。

---

## 批量命名规则

批量任务（多段 cURL、HAR 里提取出的多个媒体）按序号命名，位数随本轮最大编号补零：

| 本轮任务数 | 文件名 |
|---:|---|
| 9 | `1` … `9` |
| 10 | `01` … `10` |
| 100 | `001` … `100` |
| 1000 | `0001` … `1000` |

编号从目录里已有最大数字文件名继续，所以第二批不会覆盖第一批。例如已有 `9.mp4`，再下 3 个得到 `10`、`11`、`12`。

---

## 已知限制

- 打包时对 `yt-dlp` 固定传 `--no-check-certificates`，会跳过 HTTPS 证书校验，仅建议在可信网络中临时使用。
- `bin\ffmpeg.exe` 是 2020 年的 GPL 老构建，冷门封装格式可能不支持；需要新特性请自行替换。
- HAR 里的签名 URL、Cookie 通常有时效，抓包后要尽快下载；DRM 加密内容无法处理。
- 仅支持 Windows（内部大量使用 `subprocess.CREATE_NO_WINDOW` 与 Windows 控制台输出格式）。

---

## 第三方组件与许可

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Unlicense
- [aria2](https://github.com/aria2/aria2) — GPL-2.0
- [FFmpeg](https://ffmpeg.org/) — 本仓库附带的是 GPL 构建，分发时需遵守 GPL 条款

本项目自身代码未声明许可证，默认保留所有权利；如需开源请补 `LICENSE`。
