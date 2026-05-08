import base64
import getpass
import grp
import os

GROUP = "easypkg"
SUDOERS_PATH = "/etc/sudoers.d/easypkg"

# Разрешаем только конкретные бинарники пакетных менеджеров
_SUDOERS_CONTENT = (
    "# EasyPkg — установка пакетов без пароля для группы easypkg\n"
    "%easypkg ALL=(ALL) NOPASSWD: "
    "/usr/bin/pacman, /usr/bin/apt, /usr/bin/apt-get, "
    "/usr/bin/dnf, /bin/dnf\n"
)


def setup_done() -> bool:
    return os.path.exists(SUDOERS_PATH)


def user_in_group() -> bool:
    try:
        return getpass.getuser() in grp.getgrnam(GROUP).gr_mem
    except KeyError:
        return False


def needs_wizard() -> bool:
    return not setup_done()


def needs_password() -> bool:
    return not (setup_done() and user_in_group())


def get_setup_cmd(username: str) -> list[str]:
    # base64 чтобы избежать проблем с экранированием в shell
    content_b64 = base64.b64encode(_SUDOERS_CONTENT.encode()).decode()
    script = (
        f"groupadd -f {GROUP} && "
        f"usermod -aG {GROUP} {username} && "
        f"echo {content_b64} | base64 -d > {SUDOERS_PATH} && "
        f"chmod 440 {SUDOERS_PATH}"
    )
    return ["sh", "-c", script]
