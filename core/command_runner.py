import os
import subprocess


def run_sync(cmd: list[str], timeout: int = 30) -> tuple[str, int]:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.returncode
    except FileNotFoundError:
        return f"Команда не найдена: {cmd[0]}", 127
    except subprocess.TimeoutExpired:
        return "Превышено время ожидания", 1


try:
    from PyQt6.QtCore import QThread, pyqtSignal as _signal

    class InstallWorker(QThread):
        line_received = _signal(str)
        finished = _signal(bool)

        def __init__(self, cmd: list[str], password: str | None, parent=None):
            super().__init__(parent)
            self.cmd = cmd
            self.password = password

        def run(self):
            env = os.environ.copy()
            env["DEBIAN_FRONTEND"] = "noninteractive"
            try:
                if self.password is not None:
                    full_cmd = ["sudo", "-S"] + self.cmd
                    stdin_mode = subprocess.PIPE
                else:
                    # NOPASSWD — sudo без ввода пароля
                    full_cmd = ["sudo"] + self.cmd
                    stdin_mode = subprocess.DEVNULL

                proc = subprocess.Popen(
                    full_cmd,
                    stdin=stdin_mode,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )

                if self.password is not None:
                    proc.stdin.write(self.password + "\n")
                    proc.stdin.flush()
                    proc.stdin.close()

                for line in iter(proc.stdout.readline, ""):
                    stripped = line.rstrip()
                    if stripped:
                        self.line_received.emit(stripped)
                proc.wait()
                self.finished.emit(proc.returncode == 0)
            except Exception as e:
                self.line_received.emit(f"Ошибка: {e}")
                self.finished.emit(False)

except ImportError:
    pass
