import base64
import getpass
import os

GROUP = "easypkg"
SUDOERS_PATH = "/etc/sudoers.d/easypkg"


def setup_done() -> bool:
    """Проверяет что файл существует и содержит правило для конкретного пользователя."""
    if not os.path.exists(SUDOERS_PATH):
        return False
    try:
        content = open(SUDOERS_PATH).read()
        # Старое правило было для группы (%easypkg), новое — для пользователя
        return f"{getpass.getuser()} ALL=" in content
    except OSError:
        return False


def needs_wizard() -> bool:
    return not setup_done()


def needs_password() -> bool:
    # Правило пишется на конкретного пользователя — достаточно проверить файл
    return not setup_done()


def get_setup_cmd(username: str) -> list[str]:
    # Правило на username, а не на группу: работает сразу без re-login
    content = (
        f"# EasyPkg — установка пакетов без пароля для {username}\n"
        f"{username} ALL=(ALL) NOPASSWD: "
        "/usr/bin/pacman, /usr/bin/apt, /usr/bin/apt-get, "
        "/usr/bin/dnf, /bin/dnf\n"
    )
    content_b64 = base64.b64encode(content.encode()).decode()
    # Группу всё равно создаём — для порядка
    script = (
        f"groupadd -f {GROUP} && "
        f"usermod -aG {GROUP} {username} && "
        f"echo {content_b64} | base64 -d > {SUDOERS_PATH} && "
        f"chmod 440 {SUDOERS_PATH}"
    )
    return ["sh", "-c", script]
