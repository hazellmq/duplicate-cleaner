#!/usr/bin/env python3
"""
🧹 Duplicate Cleaner — 智能文件去重整理工具
===========================================
功能:
  - SHA256 精确去重
  - 文件名模糊匹配
  - 自动归类整理
  - 详细报告输出

用法:
  python cleaner.py --scan <目录> [--dedupe] [--organize] [--report]

作者: 千千 🤖
"""

import os
import sys
import hashlib
import argparse
import shutil
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── 颜色工具 ──────────────────────────────────

class Colors:
    """终端颜色输出"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

def c(text, color=""):
    """带颜色的输出"""
    return f"{color}{text}{Colors.END}"

# ── 文件归类规则 ──────────────────────────────

FILE_CATEGORIES = {
    "📷 图片": ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.heic', '.raw', '.psd'],
    "📄 文档": ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.csv',
               '.json', '.xml', '.yaml', '.yml', '.log', '.rtf', '.epub', '.mobi'],
    "🎵 音频": ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus'],
    "🎬 视频": ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'],
    "📦 压缩包": ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.zst', '.iso'],
    "🛠️ 安装包": ['.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.AppImage'],
    "💻 代码": ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
               '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.sql', '.sh', '.bat'],
    "❓ 其他": [],
}

def categorize_file(ext):
    """根据扩展名归类"""
    ext = ext.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "❓ 其他"

def format_size(size_bytes):
    """人性化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def format_duration(seconds):
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds//60}m {seconds%60:.0f}s"
    else:
        return f"{seconds//3600}h {(seconds%3600)//60}m"

# ── 核心扫描引擎 ─────────────────────────────

def get_file_hash(filepath, chunk_size=8192):
    """计算文件的 SHA256 哈希"""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (IOError, PermissionError, OSError) as e:
        return None

def scan_files(root_dir, min_size=0, max_size=None):
    """递归扫描目录，返回文件列表"""
    files = []
    root = Path(root_dir)
    if not root.exists():
        print(c(f"❌ 目录不存在: {root_dir}", Colors.RED))
        sys.exit(1)

    total = 0
    for path in root.rglob('*'):
        if path.is_file():
            total += 1

    print(c(f"\n📁 正在扫描: {root_dir}", Colors.BOLD))
    print(c(f"   共计 {total} 个文件，请稍候...", Colors.DIM))

    count = 0
    for path in root.rglob('*'):
        if path.is_file():
            count += 1
            size = path.stat().st_size
            if min_size > 0 and size < min_size:
                continue
            if max_size and size > max_size:
                continue
            files.append({
                'path': path,
                'size': size,
                'ext': path.suffix.lower(),
                'name': path.name,
                'category': categorize_file(path.suffix),
            })
            if count % 500 == 0 or count == total:
                pct = int(count / total * 100) if total > 0 else 0
                bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
                print(c(f"   ⏳ [{bar}] {count}/{total} ({pct}%)", Colors.DIM), end='\r')

    print(c(f"   ✅ 扫描完成: {len(files)} 个有效文件          ", Colors.GREEN))
    return files

def find_duplicates_by_hash(files):
    """基于 SHA256 哈希查找精确重复文件"""
    print(c("\n🔍 正在计算文件哈希 (SHA256)...", Colors.BOLD))

    hash_map = defaultdict(list)
    count = 0
    total = len(files)

    for f in files:
        count += 1
        if count % 100 == 0 or count == total:
            pct = int(count / total * 100) if total > 0 else 0
            bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
            print(c(f"   ⏳ [{bar}] {count}/{total} ({pct}%)", Colors.DIM), end='\r')

        file_hash = get_file_hash(f['path'])
        if file_hash:
            hash_map[file_hash].append(f)

    print(c(f"   ✅ 哈希计算完成                        ", Colors.GREEN))

    # 找出有重复的
    duplicates = {h: flist for h, flist in hash_map.items() if len(flist) > 1}
    return duplicates

def find_duplicates_by_name(files):
    """基于文件名和大小查找可能重复（文件名相同且大小相近）"""
    print(c("\n🔍 正在基于文件名查找可能重复...", Colors.BOLD))

    name_map = defaultdict(list)
    for f in files:
        key = (f['name'].lower(), f['size'])  # 同名同大小
        name_map[key].append(f)

    duplicates = {k: v for k, v in name_map.items() if len(v) > 1}
    return duplicates

# ── 操作引擎 ─────────────────────────────────

def save_report(report_data, root_dir):
    """保存扫描报告"""
    report_path = Path(root_dir) / ".duplicate_cleaner_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
    return report_path

def print_report(duplicates_by_hash, duplicates_by_name, files, root_dir, 
                 removed_count=0, removed_size=0, organized_count=0):
    """打印漂亮报告"""
    print()
    print(c("╔══════════════════════════════════════════════╗", Colors.CYAN))
    print(c("║   🧹 Duplicate Cleaner - 扫描报告             ║", Colors.CYAN))
    print(c("╚══════════════════════════════════════════════╝", Colors.CYAN))
    print()

    print(c(f"📁 扫描目录: {root_dir}", Colors.BOLD))
    print(c(f"📊 总文件数: {len(files)}", Colors.BLUE))

    # 归类统计
    category_counts = defaultdict(lambda: {'count': 0, 'size': 0})
    for f in files:
        cat = f['category']
        category_counts[cat]['count'] += 1
        category_counts[cat]['size'] += f['size']

    print(c(f"📂 文件归类统计:", Colors.BOLD))
    for cat in sorted(category_counts.keys()):
        info = category_counts[cat]
        if info['count'] > 0:
            print(f"  {cat}: {info['count']} 个 ({format_size(info['size'])})")

    # 哈希重复
    hash_dup_count = sum(len(v) for v in duplicates_by_hash.values())
    hash_dup_groups = len(duplicates_by_hash)
    hash_dup_size = sum(
        (len(v) - 1) * v[0]['size']
        for v in duplicates_by_hash.values()
    )

    print()
    print(c(f"🔁 SHA256 精确重复: {hash_dup_groups} 组, {hash_dup_count} 个副本", Colors.YELLOW))
    print(c(f"💾 可节省空间: {format_size(hash_dup_size)}", Colors.GREEN))

    if hash_dup_groups > 0:
        print()
        print(c("📋 重复文件详情 (仅显示前10组):", Colors.BOLD))
        for i, (h, flist) in enumerate(list(duplicates_by_hash.items())[:10]):
            if i >= 10:
                break
            print(c(f"\n  [{i+1}] SHA256: {h[:16]}... {format_size(flist[0]['size'])}", Colors.DIM))
            for j, f in enumerate(flist):
                marker = c(" ★ 保留", Colors.GREEN) if j == 0 else c(" ✗ 可删", Colors.RED)
                print(f"      {'📄' if j == 0 else '📋'} {f['path'].relative_to(root_dir)}{marker}")

    # 按名重复 — 排除已被哈希去重覆盖的
    total_name_dup_files = sum(len(v) for v in duplicates_by_name.values())
    name_dup_groups = len(duplicates_by_name)
    # 合并所有哈希重复中的文件path集合，用于去重统计
    hash_dup_paths = set()
    for flist in duplicates_by_hash.values():
        for f in flist:
            hash_dup_paths.add(f['path'])

    extra_by_name = 0
    for flist in duplicates_by_name.values():
        for f in flist:
            if f['path'] not in hash_dup_paths:
                extra_by_name += 1

    if extra_by_name > 0:
        print()
        print(c(f"📝 同名同大小候选 (不包含已统计的哈希重复): {extra_by_name} 个", Colors.YELLOW))

    # 操作统计
    print()
    if removed_count > 0:
        print(c(f"🗑️ 已删除重复文件: {removed_count} 个", Colors.GREEN))
        print(c(f"💾 实际节省空间: {format_size(removed_size)}", Colors.GREEN))
    if organized_count > 0:
        print(c(f"📁 已归类整理: {organized_count} 个文件", Colors.BLUE))

    print()


def deduplicate(duplicates_by_hash, root_dir, dry_run=True):
    """去重：保留第一个（最旧）文件，删除其余副本"""
    removed_count = 0
    removed_size = 0
    root = Path(root_dir)

    print()
    if dry_run:
        print(c("🔍 [预览模式] 以下文件将被删除（不实际执行）", Colors.YELLOW))
    else:
        print(c("🗑️  正在删除重复文件...", Colors.RED))

    for h, flist in duplicates_by_hash.items():
        # 按修改时间排序，保留最早的文件
        sorted_files = sorted(flist, key=lambda x: x['path'].stat().st_mtime if x['path'].exists() else 0)
        keep = sorted_files[0]  # 保留第一个（最旧）

        for f in sorted_files[1:]:
            rel_path = f['path'].relative_to(root)
            rel_keep = keep['path'].relative_to(root)

            if f['path'] == keep['path']:
                continue

            if dry_run:
                print(f"  📋 {rel_path}")
                print(f"     ↳ 同副本为: {rel_keep} ({format_size(f['size'])})")
            else:
                try:
                    os.remove(f['path'])
                    print(c(f"  ✅ 已删除: {rel_path}", Colors.GREEN))
                    removed_count += 1
                    removed_size += f['size']
                except OSError as e:
                    print(c(f"  ❌ 删除失败: {rel_path} — {e}", Colors.RED))

    if not dry_run:
        print(c(f"\n✅ 完成! 删除了 {removed_count} 个文件, 节省 {format_size(removed_size)}", Colors.GREEN))

    return removed_count, removed_size

def organize(files, root_dir, dry_run=True, mode='copy'):
    """按类别整理文件到分类文件夹"""
    root = Path(root_dir)
    organized_count = 0

    print()
    if dry_run:
        print(c(f"🔍 [预览模式] 将按以下方式整理文件", Colors.YELLOW))
    else:
        mode_verb = "移动" if mode == 'move' else "复制"
        print(c(f"📁 正在{mode_verb}文件到分类文件夹...", Colors.BLUE))

    cat_dirs = {}
    for cat in FILE_CATEGORIES.keys():
        cat_dir = root / cat.split(' ')[-1]
        cat_dirs[cat] = cat_dir

    for f in files:
        cat = f['category']
        dest_dir = cat_dirs[cat]
        dest_path = dest_dir / f['name']

        # 处理同名文件
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            dest_path = dest_dir / f"{stem}_dedup_{os.urandom(2).hex()}{suffix}"

        rel_src = f['path'].relative_to(root)
        rel_dst = dest_path.relative_to(root)

        if dry_run:
            print(f"  📄 {rel_src}")
            print(f"     ↳ {rel_dst}")
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if mode == 'move':
                    shutil.move(str(f['path']), str(dest_path))
                else:
                    shutil.copy2(str(f['path']), str(dest_path))
                organized_count += 1
            except OSError as e:
                print(c(f"  ❌ 整理失败: {rel_src} — {e}", Colors.RED))

    if not dry_run:
        print(c(f"\n✅ 完成! 整理了 {organized_count} 个文件", Colors.GREEN))

    return organized_count

# ── 主入口 ───────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='🧹 Duplicate Cleaner — 智能文件去重整理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cleaner.py --scan .                     # 仅扫描预览
  python cleaner.py --scan . --dedupe             # 扫描+去重
  python cleaner.py --scan . --organize            # 扫描+整理
  python cleaner.py --scan . --dedupe --organize   # 全流程
  python cleaner.py --scan . --dry-run             # 安全预览模式(默认)
        """
    )

    parser.add_argument('--scan', '-s', required=True,
                        help='要扫描的目录路径')
    parser.add_argument('--dedupe', '-d', action='store_true',
                        help='去重模式（删除重复文件）')
    parser.add_argument('--organize', '-o', action='store_true',
                        help='整理模式（按类别归类文件）')
    parser.add_argument('--report', '-r', action='store_true',
                        help='生成报告文件')
    parser.add_argument('--no-dry-run', action='store_true',
                        help='关闭预览模式（直接执行操作）')
    parser.add_argument('--dry-run', '-n', action='store_true', default=False,
                        help='预览模式（默认直接操作，加此参数只预览不执行）')
    parser.add_argument('--move', action='store_true',
                        help='整理时移动文件而非复制（与--organize配合）')
    parser.add_argument('--min-size', type=int, default=0,
                        help='最小文件大小（字节），小于此值忽略')
    parser.add_argument('--max-mb', type=float, default=0,
                        help='最大文件大小（MB），大于此值忽略')

    args = parser.parse_args()

    start_time = datetime.now()
    root_dir = os.path.abspath(args.scan)

    print(c(f"""
╔══════════════════════════════════════════════╗
║   🧹 Duplicate Cleaner v1.0                  ║
║   智能文件去重整理工具                         ║
╚══════════════════════════════════════════════╝
""", Colors.CYAN))

    # 参数设置
    max_size = args.max_mb * 1024 * 1024 if args.max_mb > 0 else None

    # 扫描
    print(c("📡 第一步: 扫描文件", Colors.BOLD))
    files = scan_files(root_dir, min_size=args.min_size, max_size=max_size)

    if not files:
        print(c("\n⚠️  没有找到文件", Colors.YELLOW))
        return

    # 哈希去重
    print(c("\n📡 第二步: 查找重复文件", Colors.BOLD))
    dups_hash = find_duplicates_by_hash(files)
    dups_name = find_duplicates_by_name(files)

    # 决定是否实际执行
    dry_run = not args.no_dry_run and args.dry_run

    # 去重
    removed_count = 0
    removed_size = 0
    if args.dedupe and dups_hash:
        dedupe_dry_run = dry_run
        if dedupe_dry_run:
            print(c("\n⚠️  当前为预览模式，如需实际删除请加 --no-dry-run", Colors.YELLOW))
        removed_count, removed_size = deduplicate(dups_hash, root_dir, dry_run=dedupe_dry_run)

    # 整理
    organized_count = 0
    if args.organize:
        organize_mode = 'move' if args.move else 'copy'
        organized_count = organize(files, root_dir, dry_run=dry_run, mode=organize_mode)

    # 打印报告
    print(c("\n📡 第三步: 生成报告", Colors.BOLD))
    print_report(dups_hash, dups_name, files, root_dir,
                 removed_count, removed_size, organized_count)

    # 保存报告
    if args.report:
        report_data = {
            'scan_time': str(start_time),
            'duration': str(datetime.now() - start_time),
            'root_dir': root_dir,
            'total_files': len(files),
            'duplicate_groups': len(dups_hash),
            'duplicate_files': sum(len(v) for v in dups_hash.values()),
            'savable_size': sum((len(v) - 1) * v[0]['size'] for v in dups_hash.values()),
            'removed_count': removed_count,
            'removed_size': removed_size,
            'organized_count': organized_count,
        }
        report_path = save_report(report_data, root_dir)
        print(c(f"\n📄 报告已保存: {report_path}", Colors.DIM))
    else:
        # 没传 --report 时给个提示
        print(c("\n💡 如需生成JSON报告文件，请加 --report 参数", Colors.DIM))

    elapsed = (datetime.now() - start_time).total_seconds()
    print(c(f"\n⏱️  总耗时: {format_duration(elapsed)}", Colors.DIM))
    print(c("\n✨ 完成! 你的文件世界更清爽了 🧹\n", Colors.GREEN))

if __name__ == '__main__':
    main()
