#!/usr/bin/env python3
"""Repair CrossOver's certificate-chain choice for Korean Overwatch.

The package changes one selected bottle only.  It does not patch game files,
disable signature checks, or modify the macOS trust store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PATCH_ID = "overwatch-nexon-crossover-cert-chain-v1"
CROSS_SHA1 = "A99D5B79E9F1CDA59CDAB6373169D5353F5874C6"
SELF_G4_SHA1 = "DDFB16CD4931C973A2037D3FC83A4D7D775D05E4"
PIN_SHA1 = "0563B8630D62D75ABBC8AB1E4BDFB5A899B24D43"
PACKAGE = Path(__file__).resolve().parent
DEFAULT_BOTTLES = Path.home() / "Library/Application Support/CrossOver/Bottles"
ENGINE_FILES = (
    "bin/wineloader",
    "CrossOver-Hosted Application/wineloader",
    "lib/wine/x86_64-unix/wine",
)
CONFIG_KEYS = (
    ("EnvironmentVariables", "DYLD_INSERT_LIBRARIES"),
    ("EnvironmentVariables", "CX_ROOT"),
    ("Wine", "BinPath"),
    ("Wine", "LibPath"),
)
MENU_FILE = "cxmenu.conf"
MENU_LAUNCHERS = frozenset(("battle.net.lnk", "overwatch.lnk", "오버워치.lnk"))
VALUE_RE = re.compile(r'^\s*"([^"\r\n]+)"\s*=\s*"([^"\r\n]*)"\s*$')
SECTION_RE = re.compile(r"^\[([^\]\r\n]+)\]\s*$")


class PatchError(Exception):
    pass


def run(argv: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, capture_output=capture)
    if result.returncode:
        details = (result.stderr or result.stdout or "").strip()
        raise PatchError(f"명령 실패 ({result.returncode}): {argv[0]} {details[-1200:]}")
    return result


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def reject_unsupported_path(path: Path) -> None:
    # CXConfig's quoted fields, path lists, and the compiler -D literal must
    # retain the selected path without escape/expansion ambiguity.
    if any(char in str(path) for char in ('"', "\\", ":", "$", "\n", "\r", "\0")):
        raise PatchError(f"이 경로에는 지원하지 않는 문자가 있습니다: {path}")


def find_app(given: str | None) -> Path:
    candidates = [Path(given)] if given else [Path("/Applications/CrossOver.app"),
                                             Path.home() / "Applications/CrossOver.app"]
    for path in candidates:
        app = path.expanduser().resolve()
        info = app / "Contents/Info.plist"
        if not info.is_file():
            continue
        data = plistlib.loads(info.read_bytes())
        if data.get("CFBundleIdentifier") != "com.codeweavers.CrossOver":
            continue
        root = app / "Contents/SharedSupport/CrossOver"
        if not (root / "bin/wine").is_file() or not (root / "bin/wineserver").is_file():
            raise PatchError("CrossOver Wine 실행 파일을 찾지 못했습니다")
        for relative in ENGINE_FILES:
            if not (root / relative).is_file():
                raise PatchError(f"CrossOver 실행 파일 없음: {relative}")
        reject_unsupported_path(root)
        return root
    raise PatchError("/Applications 또는 ~/Applications에서 CrossOver.app을 찾지 못했습니다")


def find_bottle(given: str | None, *, require_game: bool = True) -> Path:
    if given:
        bottle = Path(given).expanduser().resolve()
    else:
        matches = [path for path in DEFAULT_BOTTLES.iterdir()
                   if path.is_dir() and
                   ((path / "drive_c/Program Files (x86)/Overwatch/_retail_/Overwatch.exe").is_file()
                    if require_game else (path / "overwatch-cert-fix/fix-manifest.json").is_file())]
        if len(matches) != 1:
            raise PatchError(f"오버워치 보틀 {len(matches)}개 발견. --bottle-dir로 대상 보틀을 지정하세요")
        bottle = matches[0].resolve()
    if bottle.parent != DEFAULT_BOTTLES.resolve():
        raise PatchError("기본 CrossOver Bottles 폴더의 보틀만 지원합니다")
    if not bottle.is_dir() or not (bottle / "cxbottle.conf").is_file():
        raise PatchError("CrossOver 보틀 설정을 찾지 못했습니다")
    game = bottle / "drive_c/Program Files (x86)/Overwatch/_retail_"
    if require_game and (not (game / "Overwatch.exe").is_file() or
                         not (game / "gamescale64.dll").is_file()):
        raise PatchError("_retail_의 Overwatch.exe와 gamescale64.dll이 필요합니다")
    text = (bottle / "cxbottle.conf").read_text()
    if not re.search(r'^"WineArch"\s*=\s*"win64"\s*$', text, re.M):
        raise PatchError("64비트 CrossOver 보틀만 지원합니다")
    reject_unsupported_path(bottle)
    return bottle


def expected_values(bottle: Path) -> dict[tuple[str, str], str]:
    fix = bottle / "overwatch-cert-fix"
    root = fix / "runtime"
    return {
        ("EnvironmentVariables", "DYLD_INSERT_LIBRARIES"): str(fix / "filter-root.dylib"),
        ("EnvironmentVariables", "CX_ROOT"): str(root),
        ("Wine", "BinPath"): f"{root}/bin:${{CX_ROOT}}/bin",
        ("Wine", "LibPath"): f"{root}/lib:${{CX_ROOT}}/lib",
    }


def config_values(content: str) -> dict[tuple[str, str], str]:
    values = {}
    section = ""
    for line in content.splitlines():
        match = SECTION_RE.fullmatch(line)
        if match:
            section = match.group(1)
            continue
        match = VALUE_RE.fullmatch(line)
        if match:
            key = (section, match.group(1))
            if key in values:
                raise PatchError(f"중복된 보틀 설정: {section}/{key[1]}")
            values[key] = match.group(2)
    return values


def set_config(content: str, desired: dict[tuple[str, str], str]) -> str:
    lines = content.splitlines(keepends=True)
    for section, name in desired:
        value = desired[(section, name)]
        if any(char in value for char in ('"', "\\", "\n", "\r")):
            raise PatchError("보틀 설정 값에 지원하지 않는 문자가 있습니다")
        current_section = ""
        found = False
        for i, line in enumerate(lines):
            match = SECTION_RE.fullmatch(line.rstrip("\r\n"))
            if match:
                current_section = match.group(1)
            match = VALUE_RE.fullmatch(line.rstrip("\r\n"))
            if match and (current_section, match.group(1)) == (section, name):
                if match.group(2) != value:
                    raise PatchError(f"기존 설정과 충돌: {section}/{name}")
                found = True
                break
        if found:
            continue
        starts = [i for i, line in enumerate(lines)
                  if SECTION_RE.fullmatch(line.rstrip("\r\n")) and
                  SECTION_RE.fullmatch(line.rstrip("\r\n")).group(1) == section]
        if not starts:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines += ["\n", f"[{section}]\n"]
            starts = [len(lines) - 1]
        index = starts[-1] + 1
        while index < len(lines) and not SECTION_RE.fullmatch(lines[index].rstrip("\r\n")):
            index += 1
        lines.insert(index, f'"{name}" = "{value}"\n')
    return "".join(lines)


def remove_config(content: str, desired: dict[tuple[str, str], str]) -> tuple[str, list[str]]:
    kept = []
    changed = []
    section = ""
    for line in content.splitlines(keepends=True):
        heading = SECTION_RE.fullmatch(line.rstrip("\r\n"))
        if heading:
            section = heading.group(1)
        value = VALUE_RE.fullmatch(line.rstrip("\r\n"))
        key = (section, value.group(1)) if value else None
        if key in desired:
            if value.group(2) == desired[key]:
                changed.append(f"{section}/{key[1]}")
                continue
            print(f"보존: 사용자가 변경한 {section}/{key[1]}")
        kept.append(line)
    return "".join(kept), changed


def cxmenu_values(content: str) -> dict[tuple[str, str], str]:
    """Read cxmenu.conf's section/key values and reject duplicate entries."""
    return config_values(content)


def cxmenu_remove_spaces(section: str) -> str:
    """Match CXMenuWindows::remove_spaces for its generated launcher path."""
    encoded = []
    for char in section:
        if char == " ":
            encoded.append("+")
        elif char in "+^":
            encoded.append(f"^{ord(char):02X}")
        else:
            encoded.append(char)
    return "".join(encoded)


def menu_target_sections(bottle: Path, content: str) -> list[str]:
    sections = []
    for line in content.splitlines():
        match = SECTION_RE.fullmatch(line)
        if not match:
            continue
        section = match.group(1)
        if section.rsplit("/", 1)[-1].casefold() in MENU_LAUNCHERS:
            script = bottle / "desktopdata/cxmenu" / cxmenu_remove_spaces(section)
            if not script.is_file():
                raise PatchError(f"CrossOver 메뉴 실행 파일을 찾지 못했습니다: {script}")
            sections.append(section)
    if not any(section.rsplit("/", 1)[-1].casefold() == "battle.net.lnk" for section in sections):
        raise PatchError("cxmenu.conf에 Battle.net.lnk 메뉴 항목이 없습니다")
    return sections


def menu_command(bottle: Path, section: str) -> str:
    script = bottle / "desktopdata/cxmenu" / cxmenu_remove_spaces(section)
    reject_unsupported_path(script)
    if "'" in str(script):
        raise PatchError(f"CrossOver 메뉴 경로에 지원하지 않는 문자가 있습니다: {script}")
    return f"'{script}'"


def menu_values_for_sections(bottle: Path, sections: list[str]) -> dict[tuple[str, str], str]:
    desired = {}
    for section in sections:
        desired[(section, "Type")] = "Raw"
        desired[(section, "Command")] = menu_command(bottle, section)
    return desired


def update_menu_values(content: str, desired: dict[tuple[str, str], str | None]) -> str:
    """Set or remove named cxmenu values while preserving every other line."""
    values = cxmenu_values(content)
    lines = content.splitlines(keepends=True)
    output = []
    section = ""
    seen = set()
    for line in lines:
        heading = SECTION_RE.fullmatch(line.rstrip("\r\n"))
        if heading:
            section = heading.group(1)
        value = VALUE_RE.fullmatch(line.rstrip("\r\n"))
        key = (section, value.group(1)) if value else None
        if key in desired:
            seen.add(key)
            replacement = desired[key]
            if replacement is None:
                continue
            output.append(f'"{key[1]}" = "{replacement}"\n')
            continue
        output.append(line)
    for key, replacement in desired.items():
        if replacement is None or key in seen:
            continue
        section, name = key
        if key in values:
            raise PatchError(f"중복된 cxmenu 설정: {section}/{name}")
        for index, line in enumerate(output):
            heading = SECTION_RE.fullmatch(line.rstrip("\r\n"))
            if heading and heading.group(1) == section:
                insert = index + 1
                while insert < len(output) and not SECTION_RE.fullmatch(output[insert].rstrip("\r\n")):
                    insert += 1
                output.insert(insert, f'"{name}" = "{replacement}"\n')
                break
        else:
            raise PatchError(f"cxmenu 섹션을 찾지 못했습니다: {section}")
    return "".join(output)


def menu_metadata(bottle: Path, content: str, manifest: dict) -> tuple[dict, dict[tuple[str, str], str]]:
    """Validate or create the manifest-owned menu patch plan."""
    sections = menu_target_sections(bottle, content)
    desired = menu_values_for_sections(bottle, sections)
    menu = manifest.get("menu_patch")
    if menu is None:
        values = cxmenu_values(content)
        # A pre-existing Raw/Command pair is only accepted when it is the exact
        # wrapper this installer would own; anything else might be user setup.
        for key, value in desired.items():
            actual = values.get(key)
            if key[1] == "Type" and actual not in (None, "Windows", value):
                raise PatchError(f"기존 cxmenu 설정과 충돌: {key[0]}/{key[1]}")
            if key[1] == "Command" and actual not in (None, value):
                raise PatchError(f"기존 cxmenu 설정과 충돌: {key[0]}/{key[1]}")
        original = {f"{section}\t{name}": values.get((section, name))
                    for section, name in desired}
        menu = {
            "path": str(bottle / MENU_FILE),
            "original_values": original,
            "patched_values": {f"{section}\t{name}": value
                               for (section, name), value in desired.items()},
        }
        manifest["menu_patch"] = menu
    if not isinstance(menu, dict) or menu.get("path") != str(bottle / MENU_FILE):
        raise PatchError("메뉴 패치 설치 기록이 이 보틀과 일치하지 않습니다")
    stored = menu.get("patched_values")
    original = menu.get("original_values")
    if not isinstance(stored, dict) or not isinstance(original, dict):
        raise PatchError("메뉴 패치 설치 기록이 손상되었습니다")
    stored_desired = {}
    for encoded, value in stored.items():
        if not isinstance(encoded, str) or not isinstance(value, str) or "\t" not in encoded:
            raise PatchError("메뉴 패치 설치 기록이 손상되었습니다")
        section, name = encoded.rsplit("\t", 1)
        stored_desired[(section, name)] = value
    if stored_desired != desired:
        raise PatchError("CrossOver 메뉴 항목이 설치 기록과 달라 자동 덮어쓰기를 중단합니다")
    return menu, desired


def apply_menu_patch(bottle: Path, manifest_path: Path, manifest: dict) -> None:
    path = bottle / MENU_FILE
    content = path.read_text()
    menu, desired = menu_metadata(bottle, content, manifest)
    original = menu["original_values"]
    values = cxmenu_values(content)
    for (section, name), value in desired.items():
        actual = values.get((section, name))
        previous = original.get(f"{section}\t{name}")
        if actual not in (value, previous):
            raise PatchError(f"기존 cxmenu 설정과 충돌: {section}/{name}")
    # Persist ownership before changing cxmenu.conf, including legacy installs.
    write_atomic(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    proposed = update_menu_values(content, desired)
    parsed = cxmenu_values(proposed)
    if any(parsed.get(key) != value for key, value in desired.items()):
        raise PatchError("수정한 cxmenu 설정을 다시 읽을 수 없습니다")
    write_atomic(path, proposed)


def menu_restore_content(bottle: Path, manifest: dict) -> str | None:
    menu = manifest.get("menu_patch")
    if menu is None:
        return None  # Legacy installations own no menu fields.
    if not isinstance(menu, dict):
        raise PatchError("메뉴 패치 설치 기록이 없어 자동 제거할 수 없습니다")
    stored = menu.get("patched_values")
    original = menu.get("original_values")
    if (not isinstance(stored, dict) or not isinstance(original, dict) or
        set(stored) != set(original) or
        any(value is not None and not isinstance(value, str) for value in original.values())):
        raise PatchError("메뉴 패치 설치 기록이 손상되었습니다")
    restore = {}
    path = bottle / MENU_FILE
    content = path.read_text()
    values = cxmenu_values(content)
    for encoded, patched in stored.items():
        if not isinstance(encoded, str) or not isinstance(patched, str) or "\t" not in encoded:
            raise PatchError("메뉴 패치 설치 기록이 손상되었습니다")
        section, name = encoded.rsplit("\t", 1)
        key = (section, name)
        if values.get(key) == patched:
            restore[key] = original.get(encoded)
    if restore:
        return update_menu_values(content, restore)
    return None


def restore_menu_patch(bottle: Path, manifest: dict) -> None:
    content = menu_restore_content(bottle, manifest)
    if content is not None:
        write_atomic(bottle / MENU_FILE, content)


def write_atomic(path: Path, content: str) -> None:
    temp = path.with_name(path.name + ".overwatch-fix.tmp")
    try:
        temp.write_text(content)
        temp.chmod(path.stat().st_mode)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def winereg_has(bottle: Path, store: str, thumbprint: str) -> bool:
    registry = bottle / "system.reg"
    if not registry.is_file():
        return False
    key = f"[Software\\\\Microsoft\\\\SystemCertificates\\\\{store}\\\\Certificates\\\\{thumbprint}]"
    return key in registry.read_text(errors="replace")


def validate_package() -> None:
    source = PACKAGE / "native/filter_root.c"
    helper = PACKAGE / "probe/gamescale-pin-probe.exe"
    cert = PACKAGE / "certs/digicert-g4-cross.der"
    cert_pem = PACKAGE / "certs/digicert-g4-cross.pem"
    root_pem = PACKAGE / "certs/digicert-assured-id-root.pem"
    original_root = PACKAGE / "certs/digicert-g4-self.der"
    if not all(path.is_file() for path in (source, helper, cert, cert_pem, root_pem,
                                           original_root)):
        raise PatchError("패치 파일이 누락되었습니다. ZIP을 다시 풀어 실행하세요")
    if hashlib.sha1(cert.read_bytes()).hexdigest().upper() != CROSS_SHA1:
        raise PatchError("동봉한 교차 서명 인증서의 지문이 다릅니다")
    if hashlib.sha1(original_root.read_bytes()).hexdigest().upper() != SELF_G4_SHA1:
        raise PatchError("동봉한 원래 루트 인증서의 지문이 다릅니다")
    result = run(["/usr/bin/openssl", "verify", "-CAfile", str(root_pem), str(cert_pem)], capture=True)
    if "OK" not in result.stdout:
        raise PatchError("동봉한 교차 서명 인증서 검증 실패")
    if "OVERWATCH_BOTTLE_PATH" not in source.read_text():
        raise PatchError("필터 소스가 다른 버전입니다")
    helper_bytes = helper.read_bytes()
    if any(mode not in helper_bytes for mode in (b"--remove-fix-ca",
                                                    b"--remove-redundant-root",
                                                    b"--restore-original-root")):
        raise PatchError("제한된 인증서 정리 도구가 필요합니다")


def ensure_toolchain(runtime: Path, bottle: Path) -> None:
    if sys.platform != "darwin":
        raise PatchError("macOS 전용 패치입니다")
    for tool in ("clang", "codesign", "lipo", "cp", "arch"):
        if not shutil.which(tool):
            raise PatchError(f"필요한 macOS 도구 없음: {tool}")
    run(["/usr/bin/arch", "-x86_64", "/usr/bin/true"], capture=True)
    arches = run(["/usr/bin/lipo", "-archs", str(runtime / "bin/wineloader")], capture=True).stdout.split()
    if "x86_64" not in arches:
        raise PatchError("x86_64 CrossOver Wine 로더가 필요합니다")
    if runtime.stat().st_dev != bottle.stat().st_dev:
        raise PatchError("APFS 복제를 위해 CrossOver 앱과 보틀이 같은 볼륨에 있어야 합니다")
    if shutil.disk_usage(bottle).free < 1024 * 1024 * 1024:
        raise PatchError("보틀 볼륨의 여유 공간이 1GB 미만입니다")


def clone_engine(source: Path, fix: Path) -> dict[str, str]:
    target = fix / "runtime"
    if target.exists():
        raise PatchError(f"기존 복제 엔진이 있습니다: {target}")
    original_hashes = {relative: sha256(source / relative) for relative in ENGINE_FILES}
    run(["/bin/cp", "-c", "-R", str(source), str(target)])
    entitlement_files = {}
    # CrossOver hard-links the two wineloader paths.  Check all pristine
    # copies before signing any alias of their shared inode.
    for relative in ENGINE_FILES:
        original_file = source / relative
        private_file = target / relative
        if not private_file.is_file() or sha256(private_file) != original_hashes[relative]:
            raise PatchError(f"엔진 복제 검증 실패: {relative}")
        entitlements = run(["/usr/bin/codesign", "-d", "--entitlements", "-", "--xml",
                            str(original_file)], capture=True).stdout
        if not entitlements:
            raise PatchError(f"원본 권한 추출 실패: {relative}")
        parsed = plistlib.loads(entitlements.encode())
        if not parsed.get("com.apple.security.cs.disable-library-validation"):
            raise PatchError(f"원본 권한에 라이브러리 검증 예외가 없습니다: {relative}")
        entitlement_file = fix / (relative.replace("/", "_") + ".entitlements.plist")
        entitlement_file.write_bytes(plistlib.dumps(parsed, fmt=plistlib.FMT_XML))
        entitlement_files[relative] = entitlement_file
    for relative in ENGINE_FILES:
        private_file = target / relative
        run(["/usr/bin/codesign", "--force", "--sign", "-", "--options", "0",
             "--entitlements", str(entitlement_files[relative]), str(private_file)])
    for relative in ENGINE_FILES:
        private_file = target / relative
        run(["/usr/bin/codesign", "--verify", str(private_file)])
        if sha256(source / relative) != original_hashes[relative]:
            raise PatchError(f"원본 CrossOver 실행 파일이 변경되었습니다: {relative}")
    return original_hashes


def build_filter(bottle: Path, fix: Path) -> None:
    source = PACKAGE / "native/filter_root.c"
    shutil.copy2(source, fix / source.name)
    define = "-DOVERWATCH_BOTTLE_PATH=" + json.dumps(str(bottle), ensure_ascii=False)
    target = fix / "filter-root.dylib"
    run(["/usr/bin/clang", "-arch", "x86_64", "-dynamiclib", "-Wall", "-Wextra", "-Werror",
         define, str(source), "-framework", "Security", "-framework", "CoreFoundation",
         "-o", str(target)])
    archs = run(["/usr/bin/lipo", "-archs", str(target)], capture=True).stdout.split()
    if archs != ["x86_64"]:
        raise PatchError(f"인증서 필터의 아키텍처가 잘못되었습니다: {archs}")


def backup_bottle(bottle: Path, fix: Path) -> Path:
    backup = fix / "backups" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, exist_ok=False)
    for name in ("cxbottle.conf", MENU_FILE, "system.reg", "user.reg", "userdef.reg"):
        source = bottle / name
        if source.is_file():
            shutil.copy2(source, backup / name)
    return backup


def wine_call(runtime: Path, bottle: Path, helper: Path, *arguments: str,
              expected_absent: bool = False) -> str:
    cmd = [str(runtime / "bin/wine"), "--bottle", bottle.name, "--no-gui", "--no-update",
           "--debugmsg", "-all", str(helper), *arguments]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    output = proc.stdout + proc.stderr
    if proc.returncode == 3 and expected_absent:
        return output
    if proc.returncode:
        raise PatchError(f"Wine 인증서 단계 실패 ({proc.returncode}): {output[-1800:]}")
    return output


def stop_bottle_wine(runtime: Path, bottle: Path) -> None:
    env = os.environ.copy()
    env["WINEPREFIX"] = str(bottle)
    result = subprocess.run([str(runtime / "bin/wineserver"), "-k"], env=env,
                            text=True, capture_output=True)
    # wineserver -k exits 1 with no diagnostics if this prefix has no server.
    if result.returncode and not (result.returncode == 1 and
                                  not result.stdout.strip() and not result.stderr.strip()):
        raise PatchError(f"대상 보틀의 Wine 종료 실패: {result.stderr.strip()}")


def install(runtime: Path, bottle: Path) -> None:
    validate_package()
    ensure_toolchain(runtime, bottle)
    fix = bottle / "overwatch-cert-fix"
    config = bottle / "cxbottle.conf"
    before = config.read_text()
    values = config_values(before)
    desired = expected_values(bottle)
    current = {key: values.get(key) for key in CONFIG_KEYS}
    if all(current[key] == desired[key] for key in CONFIG_KEYS):
        installed = fix / "fix-manifest.json"
        if not installed.is_file():
            raise PatchError("설정은 적용되어 있으나 이 패치의 설치 기록이 없습니다")
        manifest = json.loads(installed.read_text())
        helper = fix / "gamescale-pin-probe.exe"
        if (manifest.get("patch_id") != PATCH_ID or manifest.get("bottle") != str(bottle) or
            not helper.is_file() or sha256(helper) != manifest.get("probe_sha256") or
            not (fix / "filter-root.dylib").is_file() or
            not (fix / "runtime/bin/wineloader").is_file()):
            raise PatchError("설정은 적용되어 있으나 패치 파일 또는 설치 기록을 검증할 수 없습니다")
        run(["/usr/bin/codesign", "--verify", str(fix / "runtime/bin/wineloader")])
        apply_menu_patch(bottle, installed, manifest)
        stop_bottle_wine(runtime, bottle)
        # Wine may restore this exact root in the bottle after the first install.
        removed = wine_call(runtime, bottle, helper, "--remove-redundant-root",
                            expected_absent=True)
        if "Deleted exactly one matching certificate" in removed:
            print("다시 등록된 중복 루트 인증서를 제거했습니다.")
        stop_bottle_wine(runtime, bottle)
        dll = bottle / "drive_c/Program Files (x86)/Overwatch/_retail_/gamescale64.dll"
        output = wine_call(runtime, bottle, helper, str(dll))
        if "cElement       = 4" not in output or f"DER SHA1={PIN_SHA1}  <-- ROOT; PIN MATCH" not in output:
            raise PatchError("기존 패치 설정에서 게임 인증서 체인이 통과하지 않습니다")
        print("이미 이 보틀에 동일한 패치가 적용되어 있고 인증서 체인도 정상입니다.")
        return
    if any(current[key] is not None for key in CONFIG_KEYS):
        raise PatchError("해당 보틀에 기존 사용자 지정 Wine 경로나 DYLD 설정이 있습니다. 자동 덮어쓰기를 중단합니다")
    if fix.exists():
        raise PatchError(f"기존 패치 폴더가 있습니다. 덮어쓰지 않습니다: {fix}")

    stop_bottle_wine(runtime, bottle)
    menu_preflight = {}
    menu_metadata(bottle, (bottle / MENU_FILE).read_text(), menu_preflight)
    # The server writes system.reg at shutdown.  Snapshot after it has stopped.
    before = config.read_text()
    values = config_values(before)
    if any(values.get(key) is not None for key in CONFIG_KEYS):
        raise PatchError("Wine 종료 중 보틀 설정이 변경되었습니다. 설치를 중단합니다")
    fix.mkdir()
    backup = backup_bottle(bottle, fix)
    ca_present = winereg_has(bottle, "CA", CROSS_SHA1)
    original_root_present = winereg_has(bottle, "Root", SELF_G4_SHA1)
    original_hashes = clone_engine(runtime, fix)
    build_filter(bottle, fix)
    helper = fix / "gamescale-pin-probe.exe"
    shutil.copy2(PACKAGE / "probe/gamescale-pin-probe.exe", helper)
    shutil.copy2(PACKAGE / "certs/digicert-g4-cross.der", fix / "digicert-g4-cross.der")
    shutil.copy2(PACKAGE / "certs/digicert-g4-self.der", fix / "digicert-g4-self.der")
    manifest = {
        "patch_id": PATCH_ID,
        "bottle": str(bottle),
        "source_runtime": str(runtime),
        "source_version": plistlib.loads((runtime.parents[2] / "Contents/Info.plist").read_bytes()).get(
            "CFBundleShortVersionString"),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "backup": str(backup),
        "original_engine_hashes": original_hashes,
        "probe_sha256": sha256(helper),
        "added_ca": not ca_present,
        "original_root_present": original_root_present,
        "config_before": {f"{section}/{key}": current[(section, key)]
                          for section, key in CONFIG_KEYS},
    }
    # Record the menu values validated before creating the private runtime.
    manifest.update(menu_preflight)
    # Record ownership before the first change to the live bottle.
    manifest_path = fix / "fix-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    proposed = set_config(before, desired)
    parsed = config_values(proposed)
    if any(parsed.get(key) != value for key, value in desired.items()):
        raise PatchError("수정한 보틀 설정을 다시 읽을 수 없습니다. 설치를 중단합니다")
    stop_bottle_wine(runtime, bottle)
    write_atomic(config, proposed)
    try:
        apply_menu_patch(bottle, manifest_path, manifest)
        if not ca_present:
            output = wine_call(runtime, bottle, helper, "--add-ca", str(fix / "digicert-g4-cross.der"))
            if CROSS_SHA1 not in output:
                raise PatchError("교차 서명 인증서 가져오기 결과를 검증할 수 없습니다")
        wine_call(runtime, bottle, helper, "--remove-redundant-root", expected_absent=True)
        dll = bottle / "drive_c/Program Files (x86)/Overwatch/_retail_/gamescale64.dll"
        output = wine_call(runtime, bottle, helper, str(dll))
        if "cElement       = 4" not in output or f"DER SHA1={PIN_SHA1}  <-- ROOT; PIN MATCH" not in output:
            raise PatchError(f"4단계 인증서 체인 검증 실패: {output[-1800:]}")
        print("패치 설치 완료: 유효한 4단계 인증서 체인과 게임의 핀 값이 일치합니다.")
        print("평소처럼 CrossOver의 Battle.net에서 오버워치를 실행하세요.")
    except Exception:
        # Preserve backups and cloned runtime for diagnosis.  Restore only
        # exact patch-owned configuration and certificate values.
        stop_bottle_wine(runtime, bottle)
        write_atomic(config, remove_config(config.read_text(), desired)[0])
        try:
            restore_menu_patch(bottle, manifest)
        except PatchError as error:
            print(f"자동 복구 중 메뉴 설정 복원 실패: {error}", file=sys.stderr)
        if not ca_present:
            try:
                wine_call(runtime, bottle, helper, "--remove-fix-ca", expected_absent=True)
            except PatchError as error:
                print(f"자동 복구 중 인증서 제거 실패: {error}", file=sys.stderr)
        if original_root_present:
            try:
                wine_call(runtime, bottle, helper, "--restore-original-root",
                          str(fix / "digicert-g4-self.der"))
            except PatchError as error:
                print(f"자동 복구 중 원래 루트 복원 실패: {error}", file=sys.stderr)
        raise


def uninstall(runtime: Path, bottle: Path) -> None:
    fix = bottle / "overwatch-cert-fix"
    manifest_path = fix / "fix-manifest.json"
    if not manifest_path.is_file():
        raise PatchError("이 패치의 설치 기록이 없어 자동 제거할 수 없습니다")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("patch_id") != PATCH_ID or manifest.get("bottle") != str(bottle):
        raise PatchError("설치 기록이 이 보틀/패치와 일치하지 않습니다")
    helper = fix / "gamescale-pin-probe.exe"
    if not helper.is_file() or sha256(helper) != manifest.get("probe_sha256"):
        raise PatchError("인증서 도구가 설치 기록과 다릅니다. 자동 제거를 중단합니다")
    desired = expected_values(bottle)
    config = bottle / "cxbottle.conf"
    active = config_values(config.read_text())
    if any(active.get(key) != value for key, value in desired.items()):
        raise PatchError("패치 설정 네 항목 중 일부가 변경되거나 빠졌습니다. 다른 설정을 보존하기 위해 자동 제거를 중단합니다")
    staged, removed = remove_config(config.read_text(), desired)
    if str(fix) in staged:
        raise PatchError("보틀 설정에 패치 폴더를 참조하는 사용자 변경이 있어 자동 제거할 수 없습니다")
    original_root = fix / "digicert-g4-self.der"
    if manifest.get("original_root_present"):
        if not original_root.is_file() or hashlib.sha1(original_root.read_bytes()).hexdigest().upper() != SELF_G4_SHA1:
            raise PatchError("원래 루트 인증서 복원 파일을 검증할 수 없습니다")
    # Reject missing/malformed menu state before removing config or certificates.
    menu_restore_content(bottle, manifest)
    stop_bottle_wine(runtime, bottle)
    restore_menu_patch(bottle, manifest)
    if manifest.get("added_ca"):
        wine_call(runtime, bottle, helper, "--remove-fix-ca", expected_absent=True)
        stop_bottle_wine(runtime, bottle)
    refreshed, removed = remove_config(config.read_text(), desired)
    if str(fix) in refreshed or len(removed) != len(CONFIG_KEYS):
        raise PatchError("Wine 종료 중 패치 폴더에 대한 설정이 바뀌었습니다")
    if removed:
        write_atomic(config, refreshed)
    if manifest.get("original_root_present"):
        wine_call(runtime, bottle, helper, "--restore-original-root", str(original_root))
        stop_bottle_wine(runtime, bottle)
    print("이 패치가 추가한 설정과 인증서를 되돌렸습니다.")
    archive = bottle / ("overwatch-cert-fix-retired-" +
                        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
    fix.rename(archive)
    print(f"백업과 비활성화된 사본은 남겨 두었습니다: {archive}")


def check(runtime: Path, bottle: Path) -> None:
    validate_package()
    values = config_values((bottle / "cxbottle.conf").read_text())
    desired = expected_values(bottle)
    status = "적용됨" if all(values.get(key) == value for key, value in desired.items()) else "미적용"
    print(f"CrossOver: {runtime.parent.parent.parent}")
    print(f"보틀: {bottle}")
    print(f"패치 설정: {status}")
    print(f"공개 교차 서명 인증서: {CROSS_SHA1}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", help="CrossOver.app 경로")
    parser.add_argument("--bottle-dir", help="대상 보틀 경로")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="읽기 전용 사전 점검")
    operation.add_argument("--uninstall", action="store_true", help="패치가 추가한 항목 되돌리기")
    args = parser.parse_args()
    bottle = find_bottle(args.bottle_dir, require_game=not args.uninstall)
    if args.uninstall:
        runtime = bottle / "overwatch-cert-fix/runtime"
        if not (runtime / "bin/wine").is_file() or not (runtime / "bin/wineserver").is_file():
            raise PatchError("패치 런타임이 없어 자동 제거할 수 없습니다")
    else:
        runtime = find_app(args.app)
    if args.check:
        check(runtime, bottle)
    elif args.uninstall:
        uninstall(runtime, bottle)
    else:
        install(runtime, bottle)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PatchError, subprocess.SubprocessError) as error:
        print(f"패치 중단: {error}", file=sys.stderr)
        raise SystemExit(1)
