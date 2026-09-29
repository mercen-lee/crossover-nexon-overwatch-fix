#!/usr/bin/env python3
"""Build gamescale_pin_probe.exe without a MinGW SDK.

This script uses the installed clang to make one COFF object and the lld-link
shipped with rustup.  lld-link creates tiny, temporary export-only DLLs solely
to generate the three Windows import libraries required by the probe.  The
resulting executable imports the real kernel32.dll, crypt32.dll, and
wintrust.dll at run time; none of the temporary DLLs are distributed or used.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent
BUILD = ROOT / ".build"
SOURCE = ROOT / "gamescale_pin_probe.c"
OBJECT = BUILD / "gamescale_pin_probe.obj"
OUTPUT = ROOT / "gamescale-pin-probe.exe"

EXPORTS = {
    "kernel32": [
        "GetStdHandle", "WriteFile", "GetLastError", "GetCommandLineW",
        "ExitProcess", "WideCharToMultiByte", "CreateFileW", "GetFileSize",
        "ReadFile", "CloseHandle",
    ],
    "crypt32": [
        "CryptHashCertificate", "CertGetNameStringW", "CertOpenStore",
        "CertAddEncodedCertificateToStore", "CertCloseStore",
        "CertEnumCertificatesInStore", "CertGetCertificateContextProperty",
        "CertDeleteCertificateFromStore",
    ],
    "wintrust": [
        "WinVerifyTrust", "WTHelperProvDataFromStateData",
        "WTHelperGetProvSignerFromChain",
    ],
}


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def rust_lld_link() -> str:
    sysroot = subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip()
    candidates = sorted((pathlib.Path(sysroot) / "lib/rustlib").glob(
        "*-apple-darwin/bin/gcc-ld/lld-link"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"rustup lld-link was not found under {sysroot}")


def make_import_lib(lld: str, name: str, symbols: list[str]) -> pathlib.Path:
    definition = BUILD / f"{name}.def"
    stub = BUILD / f"{name}.dll"
    library = BUILD / f"{name}.lib"
    definition.write_text("LIBRARY " + name + ".dll\nEXPORTS\n" + "\n".join(symbols) + "\n")
    run(lld, "/dll", "/noentry", "/machine:x64", f"/def:{definition}", f"/out:{stub}", f"/implib:{library}")
    return library


def main() -> int:
    clang = shutil.which("clang")
    if not clang:
        raise RuntimeError("clang is required")
    if not SOURCE.is_file():
        raise RuntimeError(f"missing source: {SOURCE}")

    BUILD.mkdir(exist_ok=True)
    lld = rust_lld_link()
    run(clang, "--target=x86_64-w64-windows-gnu", "-std=c11", "-ffreestanding",
        "-fno-builtin", "-fno-stack-protector", "-Wall", "-Wextra", "-Werror",
        "-c", str(SOURCE), "-o", str(OBJECT))
    libraries = [make_import_lib(lld, name, symbols) for name, symbols in EXPORTS.items()]
    run(lld, "/machine:x64", "/subsystem:console", "/entry:mainCRTStartup",
        f"/out:{OUTPUT}", str(OBJECT), *(str(lib) for lib in libraries))
    print(f"built {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
