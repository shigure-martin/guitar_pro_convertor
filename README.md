# gp2pdf — Guitar Pro → PDF 一键转换工具

把 `.gp` (Guitar Pro) 文件批量转换为 PDF，**所有轨道**完整保留（五线谱 + TAB + 和弦 + 演奏标记）。

> 🎸 给买不起 Guitar Pro、但又想在论坛下载 GP 谱的人用。

---

## ✨ 特性

- 🆓 **零成本**：用同样免费开源的 [MuseScore 4 / Studio](https://musescore.org/) 作为渲染引擎（Apache 2.0）
- 📦 **零依赖**：脚本本身只用 Python 3.8+ 标准库，无需 `pip install` 任何东西
- ⬇ **首次自动下载**：找不到 MuseScore 时自动下载便携版到 `~/.gp2pdf/musescore/`，后续直接复用
- 🪟 **跨平台**：Windows / macOS / Linux 全部支持
- 📂 **批量处理**：递归遍历目录，保留子目录结构
- 🈶 **中文友好**：文件名、歌词、和弦全部 UTF-8

---

## 🚀 快速开始

### 单个文件

```bash
# 自动在同目录生成同名 .pdf
python gp2pdf.py song.gp

# 指定输出路径
python gp2pdf.py song.gp out\song.pdf
```

### 批量转换整个谱库

```bash
# 递归处理 D:\scores 下所有 .gp，保留目录结构输出到 D:\pdf_out
python gp2pdf.py --batch D:\scores D:\pdf_out
```

### 首次运行会发生什么？

如果你机器上**没有装 MuseScore**，脚本会问：

```
❓ 系统未装 MuseScore。是否自动下载便携版 (~110MB) 到用户缓存? [Y/n]:
```

输入 `Y` 后，脚本会：
1. 下载 MuseScore 4/Studio 安装包到 `~/.gp2pdf/musescore/downloads/` (默认 `MuseScore-Studio-4.7.4.260706075-x86_64.{msi,dmg,AppImage}`)
2. 解压到 `~/.gp2pdf/musescore/`
3. 之后所有转换都调用这个本地副本

之后任何路径再次运行 gp2pdf，**都不再需要网络**，秒级启动。

---

## 📦 安装（最终用户）

**前置条件**：Python 3.8 或更高版本。Python 3.10/3.11/3.12 都行。

```bash
# 1. 下载脚本
curl -O https://raw.githubusercontent.com/shigure-martin/guitar_pro_convertor/main/gp2pdf.py
# 或者直接下载 ZIP 解压

# 2. 直接跑 (首次会下载 MuseScore)
python gp2pdf.py your_song.gp
```

不需要 `pip install` 任何东西，**不需要管理员权限**。

---

## 🎛 命令参考

```
usage: gp2pdf [-h] [--batch] [--mscore MSCORE] [--no-auto-download]
              [--no-overwrite] [--setup] [--remove] [--version]
              [input] [output]

positional arguments:
  input                 输入 .gp 文件 或 目录 (与 --batch 配合)
  output                输出 .pdf (单文件时可选)

options:
  --batch, -b           把 input 当作目录递归处理
  --mscore, -m          MuseScore 可执行文件路径 (默认自动查找)
  --no-auto-download    找不到 MuseScore 时不自动下载，直接报错
  --no-overwrite        跳过已存在的 PDF 输出
  --setup               仅下载/安装 MuseScore 到缓存，不转换文件
  --remove              移除已缓存的 MuseScore
```

### 常见用法速查

| 需求 | 命令 |
|------|------|
| 单文件转换 | `python gp2pdf.py song.gp` |
| 指定输出 | `python gp2pdf.py song.gp out.pdf` |
| 批量转换 | `python gp2pdf.py --batch input_dir output_dir` |
| 用自己装的 MuseScore | `python gp2pdf.py --mscore "C:\...\MuseScore4.exe" song.gp` |
| 预先下载 MuseScore | `python gp2pdf.py --setup` |
| 清掉本地缓存 | `python gp2pdf.py --remove` |
| 禁用自动下载 | `python gp2pdf.py --no-auto-download song.gp` |

---

## 📁 缓存目录

自动下载的 MuseScore 存在：

- Windows: `C:\Users\<你>\.gp2pdf\musescore\`
- macOS / Linux: `~/.gp2pdf/musescore/`

卸载本工具时，直接删 `~/.gp2pdf/` 即可。

---

## 🎼 支持的 GP 格式

| 扩展名 | 来源 | MuseScore 支持 |
|--------|------|-----------------|
| `.gp3` | Guitar Pro 3 | ✅ 完全支持 |
| `.gp4` | Guitar Pro 4 | ✅ 完全支持 |
| `.gp5` | Guitar Pro 5 | ✅ 完全支持 |
| `.gp6` | Guitar Pro 6 | ⚠ 部分支持 |
| `.gp7` | Guitar Pro 7 | ⚠ 部分支持 |
| `.gp8` | Guitar Pro 8 | ⚠ 部分支持 |

> 论坛 90%+ 的谱子是 GP3~5，这几种都能 100% 还原。

---

## 🔧 进阶：自定义 MuseScore 版本 / URL

通过环境变量覆盖默认版本：

```bash
# Windows PowerShell
$env:GP2PDF_MUSESCORE_VERSION = "4.7.4"
$env:GP2PDF_MUSESCORE_BUILD = "260706075"
python gp2pdf.py song.gp

# Linux/macOS bash
GP2PDF_MUSESCORE_VERSION=4.7.4 GP2PDF_MUSESCORE_BUILD=260706075 python gp2pdf.py song.gp
```

或完全自定义下载 URL：

```bash
$env:GP2PDF_MUSESCORE_URL = "https://your-mirror/MuseScore-Studio-4.7.4.260706075-x86_64.msi"
```

---

## ❓ 常见问题

**Q: 一定要联网吗？**
A: 只在首次自动下载 MuseScore 时联网。之后所有转换都在本地完成。

**Q: 国内网络下载 MuseScore 慢怎么办？**
A: 自己先下好 MSI/DMG/AppImage，放到 `~/.gp2pdf/musescore/downloads/` (默认 `MuseScore-Studio-4.7.4.260706075-x86_64.{msi,dmg,AppImage}`)，文件名按默认规则，脚本会复用。或者用 `GP2PDF_MUSESCORE_URL` 指向镜像。

**Q: 转换出来的 PDF 怎么多页？**
A: 每个轨道占一页/几页，按原谱顺序。

**Q: 我已经装过 MuseScore 怎么办？**
A: 脚本会自动检测 `C:\Program Files\MuseScore 4\` 或 `C:\Program Files\MuseScore Studio\` 等标准位置，找到就直接用，不会重复下载。

**Q: 怎么卸载？**
A: `python gp2pdf.py --remove` 清缓存。脚本本身是单个 Python 文件，删了就行。

**Q: 论坛谱子是 .zip 怎么办？**
A: GP6/7/8 有时被打包成 ZIP，里面是真正的 .gp 文件。先解压再跑本工具。

---

## 📜 许可证

MIT License — 见 [LICENSE](LICENSE) 文件。

本工具**只是调用** MuseScore 4 作为渲染引擎，MuseScore 本身遵循 Apache License 2.0 (注: MuseScore 4.x 后期版本更名为 "MuseScore Studio", 仍免费)。
