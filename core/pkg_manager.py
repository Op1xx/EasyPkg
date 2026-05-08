from dataclasses import dataclass
from .command_runner import run_sync


@dataclass
class Package:
    name: str
    description: str = ""
    version: str = ""
    installed: bool = False


def _parse_pacman_search(output: str) -> list[Package]:
    # Формат: extra/vim 9.1.0-1 [installed]\n    Описание
    packages = []
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line and not line[0].isspace() and "/" in line:
            parts = line.split()
            name = parts[0].split("/", 1)[-1] if parts else ""
            version = parts[1] if len(parts) > 1 else ""
            installed = "[installed]" in line
            desc = ""
            if i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0].isspace():
                desc = lines[i + 1].strip()
                i += 1
            if name:
                packages.append(Package(name=name, description=desc, version=version, installed=installed))
        i += 1
    return packages


def _parse_apt_search(output: str) -> list[Package]:
    # Формат: vim/focal 2:8.1 amd64 [installed]\n  Описание
    packages = []
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or line.startswith(("Sorting", "Full Text", "WARNING", "NOTE")):
            i += 1
            continue
        if "/" in line and not line[0].isspace():
            parts = line.split()
            name = parts[0].split("/")[0] if parts else ""
            version = parts[1] if len(parts) > 1 else ""
            installed = "[installed" in line
            desc = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("  "):
                desc = lines[i + 1].strip()
                i += 1
            if name:
                packages.append(Package(name=name, description=desc, version=version, installed=installed))
        i += 1
    return packages


def _parse_dnf_search(output: str) -> list[Package]:
    # Формат: vim-enhanced.x86_64 : Описание
    packages = []
    for line in output.splitlines():
        if not line or line.startswith(("=", "Last metadata", "Error", "Loaded", "Warning")):
            continue
        if ":" in line and not line[0].isspace():
            name_part, _, desc = line.partition(":")
            name = name_part.strip().rsplit(".", 1)[0]  # убираем суффикс архитектуры
            if name:
                packages.append(Package(name=name, description=desc.strip()))
    return packages


def _parse_pacman_installed(output: str) -> list[Package]:
    return [
        Package(name=line.strip(), installed=True)
        for line in output.splitlines()
        if line.strip()
    ]


def _parse_apt_installed(output: str) -> list[Package]:
    packages = []
    for line in output.splitlines():
        if not line or line.startswith(("Listing", "WARNING")):
            continue
        if "/" in line:
            name = line.split("/")[0]
            parts = line.split()
            version = parts[1] if len(parts) > 1 else ""
            packages.append(Package(name=name, version=version, installed=True))
    return packages


def _parse_dnf_installed(output: str) -> list[Package]:
    packages = []
    for line in output.splitlines():
        parts = line.strip().split(None, 1)
        if parts:
            packages.append(Package(name=parts[0], version=parts[1] if len(parts) > 1 else "", installed=True))
    return packages


_MANAGERS: dict[str, dict] = {
    "pacman": {
        "search":          lambda q: ["pacman", "-Ss", q],
        "install":         lambda p: ["pacman", "-S", "--noconfirm", p],
        "remove":          lambda p: ["pacman", "-R", "--noconfirm", p],
        "list_installed":  ["pacman", "-Qq"],
        "parse_search":    _parse_pacman_search,
        "parse_installed": _parse_pacman_installed,
    },
    "apt": {
        "search":          lambda q: ["apt", "search", q],
        "install":         lambda p: ["apt", "install", "-y", p],
        "remove":          lambda p: ["apt", "remove", "-y", p],
        "list_installed":  ["apt", "list", "--installed"],
        "parse_search":    _parse_apt_search,
        "parse_installed": _parse_apt_installed,
    },
    "dnf": {
        "search":          lambda q: ["dnf", "search", q],
        "install":         lambda p: ["dnf", "install", "-y", p],
        "remove":          lambda p: ["dnf", "remove", "-y", p],
        "list_installed":  ["rpm", "-qa", "--queryformat", "%{NAME} %{VERSION}\n"],
        "parse_search":    _parse_dnf_search,
        "parse_installed": _parse_dnf_installed,
    },
}


def search_packages(manager: str, query: str) -> list[Package]:
    cfg = _MANAGERS.get(manager)
    if not cfg:
        raise ValueError(f"Неизвестный менеджер пакетов: {manager}")
    output, code = run_sync(cfg["search"](query), timeout=60)
    if code == 127:
        raise RuntimeError(f"Менеджер '{manager}' не найден в системе")
    return cfg["parse_search"](output)


def list_installed(manager: str) -> list[Package]:
    cfg = _MANAGERS.get(manager)
    if not cfg:
        raise ValueError(f"Неизвестный менеджер пакетов: {manager}")
    output, code = run_sync(cfg["list_installed"], timeout=60)
    if code == 127:
        raise RuntimeError(f"Менеджер '{manager}' не найден в системе")
    pkgs = cfg["parse_installed"](output)
    pkgs.sort(key=lambda p: p.name)
    return pkgs


def get_installed_names(manager: str) -> set[str]:
    """Возвращает множество имён установленных пакетов."""
    cfg = _MANAGERS.get(manager)
    if not cfg:
        return set()
    output, _ = run_sync(cfg["list_installed"], timeout=30)
    return {p.name for p in cfg["parse_installed"](output)}


def get_install_cmd(manager: str, package: str) -> list[str]:
    cfg = _MANAGERS.get(manager)
    if not cfg:
        return []
    return cfg["install"](package)


def get_remove_cmd(manager: str, package: str) -> list[str]:
    cfg = _MANAGERS.get(manager)
    if not cfg:
        return []
    return cfg["remove"](package)
