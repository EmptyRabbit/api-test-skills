"""Open VSX 扩展下载、解压与历史注入清理。"""

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from app.windows_loop import hidden_popen_kwargs


def python_extension_installed(extensions_dir: Path) -> bool:
    return _python_extension_dir(extensions_dir) is not None


def extract_vsix(vsix: Path, extensions_dir: Path) -> Path:
    extensions_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(vsix) as z:
        pkg = json.loads(z.read("extension/package.json"))
        folder = f"{pkg['publisher']}.{pkg['name']}-{pkg['version']}"
        dest = extensions_dir / folder
        if dest.is_dir():
            return dest
        tmp = extensions_dir / (folder + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith("extension/") or name in {"extension/", "extension"}:
                continue
            rel = name[len("extension/") :]
            target = tmp / rel
            if info.is_dir() or name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    tmp.rename(dest)
    return dest


def _open_vsx_download_url(publisher: str, name: str, target: str | None) -> str:
    if target:
        api = f"https://open-vsx.org/api/{publisher}/{name}/{target}/latest"
    else:
        api = f"https://open-vsx.org/api/{publisher}/{name}/latest"
    with urllib.request.urlopen(api, timeout=30) as resp:
        data = json.load(resp)
    url = (data.get("files") or {}).get("download")
    if not url:
        raise RuntimeError(f"Open VSX 未返回 {publisher}.{name} 的 VSIX")
    return url


def _download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _install_open_vsx_extension(
    publisher: str,
    name: str,
    extensions_dir: Path,
    *,
    target: str | None,
    cache_dir: Path,
) -> None:
    vsix = cache_dir / f"{publisher}.{name}.vsix"
    url = _open_vsx_download_url(publisher, name, target)
    _download_url(url, vsix)
    extract_vsix(vsix, extensions_dir)


def _python_extension_dir(extensions_dir: Path) -> Path | None:
    if not extensions_dir.is_dir():
        return None
    found = [p for p in extensions_dir.iterdir() if p.is_dir() and p.name.startswith("ms-python.python-")]
    return max(found, key=lambda p: p.name) if found else None


def _remove_obsolete_entries(extensions_dir: Path, needle: str) -> None:
    obsolete = extensions_dir / ".obsolete"
    if not obsolete.is_file():
        return
    try:
        data = json.loads(obsolete.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    keys = [k for k in data if needle in k.lower()]
    if not keys:
        return
    for k in keys:
        data.pop(k, None)
    if data:
        obsolete.write_text(json.dumps(data), encoding="utf-8")
    else:
        obsolete.unlink(missing_ok=True)


def _drop_magicpython(extensions_dir: Path) -> None:
    if not extensions_dir.is_dir():
        return
    for p in extensions_dir.iterdir():
        if p.is_dir() and p.name.startswith("magicstack.MagicPython-"):
            shutil.rmtree(p, ignore_errors=True)
    _remove_obsolete_entries(extensions_dir, "magicpython")


def _invalidate_user_extension_cache(user_dir: Path) -> None:
    cached = user_dir / "CachedProfilesData"
    if not cached.is_dir():
        return
    for p in cached.rglob("extensions.user.cache"):
        p.unlink(missing_ok=True)


def _strip_injected_python_grammar(extensions_dir: Path) -> None:
    """撤销早前塞进 ms-python.python 的 python 语言/语法贡献。

    code-server 自带内置扩展 vscode.python（lib/vscode/extensions/python，随
    code-server 安装自带，始终生效），本来就贡献了 language id "python" 和
    scopeName "source.python" 的 MagicPython 语法。之前往 ms-python.python 里
    注入同样的 language id / scopeName 纯属重复注册，两边打架反而谁都渲染不出
    颜色，所以这里清掉注入的部分，只留内置的那份生效。
    """
    py = _python_extension_dir(extensions_dir)
    if py is None:
        return
    pkg_path = py / "package.json"
    if not pkg_path.is_file():
        return
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(pkg, dict):
        return
    contributes = pkg.get("contributes") or {}
    langs = contributes.get("languages") or []
    grammars = contributes.get("grammars") or []
    new_langs = [lang for lang in langs if lang.get("id") != "python"]
    new_grammars = [g for g in grammars if g.get("scopeName") != "source.python"]
    if len(new_langs) == len(langs) and len(new_grammars) == len(grammars):
        return  # 没注入过，不用动
    contributes["languages"] = new_langs
    contributes["grammars"] = new_grammars
    pkg["contributes"] = contributes
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")
    (py / "syntaxes" / "python.tmLanguage.json").unlink(missing_ok=True)
    _invalidate_user_extension_cache(extensions_dir.parent / "user")


def _remove_ui_python_syntax_extension(extensions_dir: Path) -> None:
    """删掉之前手搓的 platform.python-syntax UI 扩展及其登记，同样是为了不跟内置扩展抢注。"""
    dest = extensions_dir / "platform.python-syntax-1.0.0"
    if dest.is_dir():
        shutil.rmtree(dest, ignore_errors=True)
    manifest_path = extensions_dir / "extensions.json"
    if manifest_path.is_file():
        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = None
        if isinstance(entries, list):
            filtered = [e for e in entries if (e.get("identifier") or {}).get("id") != "platform.python-syntax"]
            if len(filtered) != len(entries):
                manifest_path.write_text(json.dumps(filtered), encoding="utf-8")
    _remove_obsolete_entries(extensions_dir, "platform.python-syntax")
    _invalidate_user_extension_cache(extensions_dir.parent / "user")


def ensure_python_extensions(extensions_dir: Path, *, via_wsl: bool = False) -> None:
    extensions_dir.mkdir(parents=True, exist_ok=True)
    cache = extensions_dir.parent / "vsix-cache"
    debugpy_target = "linux-x64" if via_wsl or os.name != "nt" else "win32-x64"
    try:
        if not python_extension_installed(extensions_dir):
            _install_open_vsx_extension(
                "ms-python", "python", extensions_dir, target=None, cache_dir=cache
            )
            _install_open_vsx_extension(
                "ms-python",
                "debugpy",
                extensions_dir,
                target=debugpy_target,
                cache_dir=cache,
            )
        _strip_injected_python_grammar(extensions_dir)
        _remove_ui_python_syntax_extension(extensions_dir)
        _drop_magicpython(extensions_dir)
    except (OSError, RuntimeError, urllib.error.URLError, TimeoutError, zipfile.BadZipFile):
        return


def ensure_debugpy() -> None:
    try:
        import debugpy  # noqa: F401
        return
    except ImportError:
        pass
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "debugpy"],
            capture_output=True,
            timeout=120,
            **hidden_popen_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return
