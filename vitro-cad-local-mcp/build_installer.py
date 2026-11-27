"""Build the Windows SFX installer and source ZIP for vitro-cad-local-mcp.

Requires the official 7-Zip CLI, 7zSD.sfx from the official LZMA SDK,
and LIEF on the build host. None is needed on colleagues' computers.
The PDF guide goes into the ZIP and remains available as a standalone file;
the self-extracting EXE contains only files needed for installation.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import lief


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT
DIST = ROOT / "dist"
EXE_NAME = "VitroCAD-Local-MCP-Setup.exe"
ZIP_NAME = "vitro-cad-local-mcp.zip"
SFX_CONFIG = (
    ';!@Install@!UTF-8!\r\n'
    'Title="Vitro-CAD Local MCP"\r\n'
    'Progress="no"\r\n'
    'Directory=""\r\n'
    'RunProgram="cmd.exe /d /c \\"%%T\\bootstrap_windows.cmd\\""\r\n'
    ';!@InstallEnd@!\r\n'
).encode("utf-8")
SFX_MANIFEST = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security><requestedPrivileges xmlns="urn:schemas-microsoft-com:asm.v3">
      <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
    </requestedPrivileges></security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/></application>
  </compatibility>
</assembly>'''


def manifest_sfx(sfx: Path, target: Path) -> bytes:
    """Mark the per-user SFX as Windows 10+ aware without changing the SDK source."""
    binary = lief.PE.parse(str(sfx))
    if binary is None or not binary.has_resources:
        raise ValueError("Не удалось прочитать ресурсы 7-Zip SFX.")
    if any(node.id == 24 for node in binary.resources.childs):
        raise ValueError("У исходного SFX уже есть манифест; проверьте его вручную.")
    resource_type = lief.PE.ResourceDirectory(24)  # RT_MANIFEST
    resource_name = lief.PE.ResourceDirectory(1)   # executable manifest
    language = lief.PE.ResourceData(list(SFX_MANIFEST))
    language.id = 1033
    resource_name.add_child(language)
    resource_type.add_child(resource_name)
    binary.resources.add_child(resource_type)
    binary.write(str(target))
    built = lief.PE.parse(str(target))
    if built is None or not built.has_resources:
        raise ValueError("Не удалось проверить манифест 7-Zip SFX.")
    manifest = next((node for node in built.resources.childs if node.id == 24), None)
    if manifest is None or bytes(manifest.childs[0].childs[0].content) != SFX_MANIFEST:
        raise ValueError("Манифест 7-Zip SFX записан неверно.")
    return target.read_bytes()


def included_files() -> list[Path]:
    return [
        path for path in sorted(SOURCE.rglob("*"))
        if path.is_file()
        and not any(part in {"__pycache__", "active", "dist", "tests", ".git"} for part in path.parts)
        and path.suffix != ".pyc"
        and path.name != ".DS_Store"
    ]


def build(sevenzip: Path, sfx: Path) -> tuple[Path, Path]:
    sevenzip = sevenzip.resolve()
    sfx = sfx.resolve()
    if not sevenzip.is_file() or not sfx.is_file():
        raise FileNotFoundError("Нужны 7zz и 7zSD.sfx из официального LZMA SDK.")
    if sfx.read_bytes()[:2] != b"MZ":
        raise ValueError("Модуль SFX не является Windows PE.")
    files = included_files()
    installer_files = [path for path in files if path.suffix.lower() != ".pdf"]
    powershell = SOURCE / "install_windows.ps1"
    if not powershell.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise ValueError("Windows PowerShell 5.1 requires a UTF-8 BOM for install_windows.ps1.")
    required = {
        "plugin.json", "mcp.json", "install_windows.ps1",
        "bootstrap_windows.cmd",
        "server/truststore/__init__.py",
        "server/truststore/_windows.py",
        "third_party/truststore-LICENSE.txt",
        "runtime/packages/python-3.14.10-embed-amd64.zip",
        "runtime/packages/python-3.14.10-embed-arm64.zip",
        "runtime/packages/python-3.14.10-embed-win32.zip",
    }
    present = {str(path.relative_to(SOURCE)) for path in files}
    if missing := required - present:
        raise ValueError(f"В исходном пакете отсутствуют файлы: {sorted(missing)}")
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / ZIP_NAME
    with ZipFile(zip_path, "w") as archive:
        for path in files:
            archive.write(
                path, Path(SOURCE.name) / path.relative_to(SOURCE),
                compress_type=ZIP_STORED if path.suffix == ".zip" else ZIP_DEFLATED,
            )
    with ZipFile(zip_path) as archive:
        if bad := archive.testzip():
            raise ValueError(f"Повреждённый файл в ZIP: {bad}")

    with tempfile.TemporaryDirectory(prefix="vitro-sfx-build-") as temporary:
        stub = manifest_sfx(sfx, Path(temporary) / "7zSD-manifest.sfx")
        stage = Path(temporary) / "stage"
        stage.mkdir()
        for path in installer_files:
            target = stage / path.relative_to(SOURCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        payload = Path(temporary) / "payload.7z"
        subprocess.run(
            [str(sevenzip), "a", "-t7z", "-mx=1", str(payload), "."],
            cwd=stage, check=True, stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [str(sevenzip), "t", str(payload)],
            check=True, stdout=subprocess.DEVNULL,
        )
        exe_path = DIST / EXE_NAME
        with exe_path.open("wb") as output:
            output.write(stub)
            output.write(SFX_CONFIG)
            output.write(payload.read_bytes())
        subprocess.run(
            [str(sevenzip), "t", str(exe_path)],
            check=True, stdout=subprocess.DEVNULL,
        )
    return exe_path, zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sevenzip", type=Path, required=True)
    parser.add_argument("--sfx", type=Path, required=True)
    args = parser.parse_args()
    exe, archive = build(args.sevenzip, args.sfx)
    print(f"{exe} ({exe.stat().st_size:,} bytes)")
    print(f"{archive} ({archive.stat().st_size:,} bytes)")
