from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Windows 下 stdout 默认 GBK，无法输出 Unicode 字符。
# 这里强制改成 UTF-8，让用户的终端能看到中文/emoji。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

__version__ = "1.0.0"

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
GP_EXTENSIONS = (".gp", ".gp3", ".gp4", ".gp5", ".gp6", ".gp7", ".gp8")

# MuseScore 4 (免费 / Apache 2.0)
# 可通过环境变量 GP2PDF_MUSESCORE_VERSION 覆盖
DEFAULT_MUSESCORE_VERSION = "4.4.4"
DEFAULT_MUSESCORE_TAG = f"v{DEFAULT_MUSESCORE_VERSION}"
DOWNLOAD_BASE = (
    f"https://github.com/musescore/MuseScore/releases/download/{DEFAULT_MUSESCORE_TAG}"
)

PLATFORM_ASSETS = {
    "win": {
        "filename": f"MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.msi",
        "url": f"{DOWNLOAD_BASE}/MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.msi",
        "binary_subpath": ["MuseScore 4", "bin", "MuseScore4.exe"],
    },
    "mac": {
        "filename": f"MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.dmg",
        "url": f"{DOWNLOAD_BASE}/MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.dmg",
        "binary_subpath": ["MuseScore 4.app", "Contents", "MacOS", "mscore"],
    },
    "linux": {
        # AppImage 自带可执行, 不需解压
        "filename": f"MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.AppImage",
        "url": f"{DOWNLOAD_BASE}/MuseScore-{DEFAULT_MUSESCORE_VERSION}-x86_64.AppImage",
        "binary_subpath": [],  # AppImage 本身就是二进制
    },
}


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def detect_platform() -> str:
    """返回 'win' / 'mac' / 'linux'"""
    s = sys.platform
    if s.startswith("win"):
        return "win"
    if s == "darwin":
        return "mac"
    return "linux"


def cache_dir() -> Path:
    """用户级缓存根目录: ~/.gp2pdf/"""
    return Path.home() / ".gp2pdf"


def musescore_cache_dir() -> Path:
    return cache_dir() / "musescore"


def musescore_cache_bin() -> Path:
    """缓存中实际可调用的二进制路径。"""
    plat = detect_platform()
    if plat == "win":
        return musescore_cache_dir() / "bin" / "MuseScore4.exe"
    if plat == "mac":
        return musescore_cache_dir() / "MuseScore 4.app" / "Contents" / "MacOS" / "mscore"
    return musescore_cache_dir() / "bin" / "mscore"


# --------------------------------------------------------------------------- #
# 1) 系统已安装的 MuseScore
# --------------------------------------------------------------------------- #
def find_system_musescore() -> Optional[str]:
    """在系统标准安装位置查找 MuseScore。"""
    plat = detect_platform()
    candidates: List[str] = []

    if plat == "win":
        for pf in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if not pf:
                continue
            candidates += [
                fr"{pf}\MuseScore 4\bin\MuseScore4.exe",
                fr"{pf}\MuseScore 3\bin\MuseScore3.exe",
                fr"{pf}\MuseScore Studio\bin\MuseScore Studio.exe",
                fr"{pf}\MuseScore\bin\MuseScore.exe",
            ]
    elif plat == "mac":
        candidates += [
            "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
            "/Applications/MuseScore Studio.app/Contents/MacOS/mscore",
            "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
            "/Applications/MuseScore.app/Contents/MacOS/mscore",
        ]
    else:
        candidates += [
            "/usr/bin/mscore",
            "/usr/local/bin/mscore",
            "/opt/mscore/bin/mscore",
            "/snap/bin/mscore",
        ]

    for p in candidates:
        if p and Path(p).is_file():
            return p

    # 兜底: PATH
    for name in ("mscore", "MuseScore", "musescore", "MuseScore4"):
        hit = shutil.which(name)
        if hit:
            return hit

    return None


# --------------------------------------------------------------------------- #
# 2) 下载与解压
# --------------------------------------------------------------------------- #
def _human_bytes(n: float) -> str:
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f} {units[i]}"


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size <= 0:
        sys.stdout.write(f"\r  ↓ {_human_bytes(downloaded)}")
        sys.stdout.flush()
        return
    pct = min(100, downloaded * 100 // total_size)
    bar_len = 30
    filled = bar_len * pct // 100
    bar = "█" * filled + "░" * (bar_len - filled)
    sys.stdout.write(
        f"\r  ↓ {_human_bytes(downloaded)}/{_human_bytes(total_size)} "
        f"[{bar}] {pct}%"
    )
    sys.stdout.flush()


def download_musescore(dest_dir: Path, *, force: bool = False) -> Path:
    """下载 MuseScore 安装包到 dest_dir / downloads/ 下, 返回文件路径。"""
    plat = detect_platform()
    info = PLATFORM_ASSETS[plat]

    downloads = dest_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    archive = downloads / info["filename"]
    if archive.exists() and not force:
        print(f"  ✓ 复用已下载文件: {archive}")
        return archive

    print(f"  → URL:  {info['url']}")
    print(f"  → 保存到: {archive}")
    print("  ⏳ 正在下载 (可能需要数分钟)...")

    url = os.environ.get("GP2PDF_MUSESCORE_URL", info["url"])
    try:
        urllib.request.urlretrieve(url, str(archive), reporthook=_progress_hook)
    except (urllib.error.URLError, OSError) as e:
        if archive.exists():
            archive.unlink(missing_ok=True)
        raise RuntimeError(f"下载失败: {e}\nURL: {url}") from e

    sys.stdout.write("\n")
    print(f"  ✓ 下载完成: {_human_bytes(archive.stat().st_size)}")
    return archive


def _extract_msi(msi: Path, target_dir: Path) -> Path:
    """Windows MSI 解压。用 msiexec /a (administrative install)。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"  → 解压 MSI 到 {target_dir} (使用 msiexec /a)...")

    cmd = [
        "msiexec",
        "/a", str(msi),
        "/qn",  # 静默
        f"TARGETDIR={target_dir}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"msiexec 解压失败 (code {proc.returncode}):\n{proc.stderr or proc.stdout}"
        )

    # msiexec /a 输出的是网络安装点，里面有 "MuseScore 4/" 子目录
    extracted = target_dir / "MuseScore 4" / "bin" / "MuseScore4.exe"
    if not extracted.is_file():
        # 兜底: 深度搜索
        hits = list(target_dir.rglob("MuseScore4.exe"))
        if not hits:
            raise RuntimeError("MSI 解压成功但找不到 MuseScore4.exe")
        extracted = hits[0]
    return extracted


def _extract_dmg(dmg: Path, target_dir: Path) -> Path:
    """macOS DMG 挂载 + 拷贝 .app 到 target_dir。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"  → 挂载 DMG: {dmg}")

    proc = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", str(dmg)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"hdiutil attach 失败: {proc.stderr}")

    # 解析挂载点 (输出最后一行通常是 /Volumes/MuseScore*)
    mount_point = ""
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[parts.__len__() - 1].startswith("/Volumes/"):
            mount_point = parts[-1].strip()
            break

    if not mount_point:
        subprocess.run(["hdiutil", "detach", "mount_point"], check=False)
        raise RuntimeError(f"无法解析 DMG 挂载点: {proc.stdout}")

    print(f"  → 挂载点: {mount_point}")

    try:
        # 找 .app
        apps = [p for p in Path(mount_point).iterdir() if p.suffix == ".app"]
        if not apps:
            raise RuntimeError("DMG 内未找到 .app")
        app_src = apps[0]

        # 拷贝到目标
        app_dst = target_dir / app_src.name
        if app_dst.exists():
            shutil.rmtree(app_dst)
        shutil.copytree(app_src, app_dst)
        binary = app_dst / "Contents" / "MacOS" / "mscore"
        if not binary.is_file():
            raise RuntimeError(f"未找到二进制: {binary}")
        return binary
    finally:
        subprocess.run(["hdiutil", "detach", mount_point], check=False)


def _setup_appimage(appimage: Path, target_dir: Path) -> Path:
    """Linux AppImage 不需解压, 直接 chmod +x 即可。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    bin_path = target_dir / "mscore"
    shutil.copy(str(appimage), str(bin_path))
    bin_path.chmod(0o755)
    print(f"  ✓ AppImage 已设为可执行: {bin_path}")
    return bin_path


def install_musescore_to_cache(*, force: bool = False) -> Path:
    """下载 + 解压 MuseScore 到用户缓存, 返回二进制路径。"""
    plat = detect_platform()
    cache = musescore_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    bin_dest = musescore_cache_bin()
    if bin_dest.is_file() and not force:
        print(f"  ✓ 已存在缓存: {bin_dest}")
        return bin_dest

    archive = download_musescore(cache, force=force)
    workdir = cache / "extracted"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    if plat == "win":
        binary = _extract_msi(archive, workdir)
    elif plat == "mac":
        binary = _extract_dmg(archive, workdir)
    else:
        binary = _setup_appimage(archive, workdir / "bin")

    # 把二进制放到最终位置
    bin_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(binary), str(bin_dest))
    if plat != "win":
        bin_dest.chmod(0o755)

    print(f"  ✓ MuseScore 已就绪: {bin_dest}")
    return bin_dest


# --------------------------------------------------------------------------- #
# 3) 主流程: 确保有 MuseScore 可用
# --------------------------------------------------------------------------- #
def ensure_musescore(
    explicit: Optional[str] = None,
    *,
    auto_download: bool = True,
    interactive: bool = True,
) -> str:
    """保证返回可用的 MuseScore 可执行路径。"""
    # 1) 用户显式指定
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise FileNotFoundError(f"--mscore 指定的文件不存在: {explicit}")
        return explicit

    # 2) 系统已安装
    found = find_system_musescore()
    if found:
        print(f"  ✓ 找到系统 MuseScore: {found}")
        return found

    # 3) 缓存命中
    cached = musescore_cache_bin()
    if cached.is_file():
        print(f"  ✓ 找到缓存 MuseScore: {cached}")
        return str(cached)

    # 4) 自动下载
    if not auto_download:
        raise RuntimeError(
            "未找到 MuseScore，且已禁用自动下载。\n"
            "请安装 MuseScore 4 (https://musescore.org/) 或用 --mscore 指定路径。"
        )

    if interactive and sys.stdin.isatty():
        ans = input(
            "  ❓ 系统未装 MuseScore。是否自动下载便携版 (~110MB) 到用户缓存? [Y/n]: "
        ).strip().lower()
        if ans not in ("", "y", "yes"):
            raise RuntimeError(
                "用户取消。请安装 MuseScore 4 或用 --mscore 指定路径后重试。"
            )

    print("  → 准备自动下载 MuseScore 4...")
    return str(install_musescore_to_cache())


# --------------------------------------------------------------------------- #
# 4) 转换 GP -> PDF
# --------------------------------------------------------------------------- #
def convert_one(
    input_path: Path,
    output_path: Path,
    mscore: str,
    *,
    overwrite: bool = True,
) -> Path:
    """把单个 GP 文件转成 PDF。MuseScore 4 CLI: input -o output"""
    if not input_path.is_file():
        raise FileNotFoundError(f"找不到输入文件: {input_path}")
    if input_path.suffix.lower() not in GP_EXTENSIONS:
        raise ValueError(
            f"不是 GP 文件: {input_path.name} "
            f"(支持: {', '.join(GP_EXTENSIONS)})"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        return output_path

    cmd = [mscore, str(input_path), "-o", str(output_path)]
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=600,
    )

    if proc.returncode != 0 or not output_path.exists():
        err = (proc.stderr or proc.stdout).strip() or "(无错误输出)"
        raise RuntimeError(f"MuseScore 返回错误 (code {proc.returncode}):\n{err}")

    return output_path


def iter_gp_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in GP_EXTENSIONS:
            yield p


def convert_batch(input_dir: Path, output_dir: Path, mscore: str) -> Tuple[int, int, list]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(iter_gp_files(input_dir))
    if not files:
        print(f"⚠ 在 {input_dir} 下没有 GP 文件。")
        return 0, 0, []

    print(f"📂 输入: {input_dir}")
    print(f"📂 输出: {output_dir}")
    print(f"🎵 找到 {len(files)} 个 GP 文件\n")

    ok, fail = 0, 0
    failed = []
    for i, gp in enumerate(files, 1):
        rel = gp.relative_to(input_dir)
        out_pdf = output_dir / rel.with_suffix(".pdf")
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{i}/{len(files)}] {rel}")
        try:
            convert_one(gp, out_pdf, mscore)
            print(f"  ✓ {out_pdf}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {e}")
            fail += 1
            failed.append((gp, str(e)))

    print("\n" + "─" * 50)
    print(f"✅ 成功: {ok}    ❌ 失败: {fail}    总计: {len(files)}")
    if failed:
        print("\n失败详情:")
        for p, msg in failed:
            print(f"  - {p.name}: {msg}")
    return ok, fail, failed


# --------------------------------------------------------------------------- #
# 5) CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gp2pdf",
        description="把 Guitar Pro 文件 (.gp) 转换为 PDF (自动管理 MuseScore)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python gp2pdf.py song.gp
  python gp2pdf.py song.gp out\\song.pdf
  python gp2pdf.py --batch D:\\scores D:\\pdf_out
  python gp2pdf.py --mscore "C:\\Program Files\\MuseScore 4\\bin\\MuseScore4.exe" song.gp
  python gp2pdf.py --setup          # 仅初始化/重装 MuseScore
  python gp2pdf.py --remove         # 移除缓存的 MuseScore""",
    )
    p.add_argument("input", nargs="?", help="输入 .gp 文件 或 目录 (与 --batch 配合)")
    p.add_argument("output", nargs="?", help="输出 .pdf (单文件时可选)")
    p.add_argument("--batch", "-b", action="store_true",
                   help="把 input 当作目录递归处理")
    p.add_argument("--mscore", "-m", help="MuseScore 可执行文件路径")
    p.add_argument("--no-auto-download", action="store_true",
                   help="找不到 MuseScore 时不自动下载，直接报错")
    p.add_argument("--no-overwrite", action="store_true",
                   help="跳过已存在的 PDF 输出")
    p.add_argument("--setup", action="store_true",
                   help="仅下载/安装 MuseScore 到缓存，不转换文件")
    p.add_argument("--remove", action="store_true",
                   help="移除已缓存的 MuseScore")
    p.add_argument("--version", action="version",
                   version=f"gp2pdf {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    # 仅 --setup
    if args.setup:
        try:
            install_musescore_to_cache(force=True)
            return 0
        except Exception as e:
            print(f"❌ 安装失败: {e}")
            return 1

    # 仅 --remove
    if args.remove:
        cache = musescore_cache_dir()
        if cache.exists():
            shutil.rmtree(cache)
            print(f"🧹 已移除缓存: {cache}")
        else:
            print("缓存不存在，无需清理。")
        return 0

    # 需要 input
    if not args.input:
        build_parser().print_help()
        return 0

    # 确保有 MuseScore
    try:
        mscore = ensure_musescore(
            args.mscore,
            auto_download=not args.no_auto_download,
            interactive=True,
        )
    except (RuntimeError, FileNotFoundError) as e:
        print(f"❌ {e}")
        return 2

    print(f"\n🎼 MuseScore: {mscore}\n")

    if args.batch:
        ok, fail, _ = convert_batch(
            Path(args.input), Path(args.output), mscore,
        )
        return 0 if fail == 0 else 1

    input_path = Path(args.input)
    output_path = (
        Path(args.output) if args.output else input_path.with_suffix(".pdf")
    )
    try:
        convert_one(
            input_path, output_path, mscore,
            overwrite=not args.no_overwrite,
        )
        print(f"✅ 完成: {output_path}")
        return 0
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
