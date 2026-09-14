"""Initialize only Compose-managed volumes; never prints credentials."""

import fcntl
import os
from pathlib import Path
import secrets
import stat


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _existing_secret_matches(path, value):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    with os.fdopen(fd, "r", encoding="utf-8") as existing:
        if not stat.S_ISREG(os.fstat(existing.fileno()).st_mode) or existing.read(16385).strip() != value:
            raise RuntimeError("Existing credential does not match the prepared profile")
    return True


def _remove_pending(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("Prepared credential must be a regular file")
    path.unlink()


def write_secret(path, value, mode=0o400):
    path = Path(path)
    pending = path.with_name(".palimpsest-" + path.name + ".pending")
    lock_path = path.parent / ".palimpsest-credentials.lock"
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        # Only this exact reserved pathname is cleaned, never other volume files.
        # The lock prevents a retry from removing another init's active write.
        _remove_pending(pending)
        if _existing_secret_matches(path, value):
            _fsync_directory(path.parent)
            return
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                os.fchmod(output.fileno(), mode)
                output.write(value + "\n")
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(pending, path, follow_symlinks=False)
            except FileExistsError:
                _existing_secret_matches(path, value)
            _fsync_directory(path.parent)
        finally:
            _remove_pending(pending)
            _fsync_directory(path.parent)


def main():
    admin, app = Path("/run/admin"), Path("/run/app")
    artifacts = Path("/var/lib/palimpsest/artifacts")
    for path in (admin, app, artifacts):
        if path.is_symlink():
            raise RuntimeError("Volume root must not be a symlink")
        path.mkdir(parents=True, exist_ok=True)
    def password(name):
        path = admin / name
        if path.is_symlink():
            raise RuntimeError("Secret must be a regular file")
        if path.exists():
            value = path.read_text().strip()
            if not value or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in value):
                raise RuntimeError("Invalid prepared credential")
            return value
        value = secrets.token_urlsafe(32)
        write_secret(path,value,0o444 if name == "postgres_password" else 0o400)
        return value
    postgres_password = password("postgres_password")
    runtime_password = password("runtime_password")
    write_secret(admin / "admin_dsn", f"host=db dbname=palimpsest user=postgres password={postgres_password}")
    write_secret(app / "runtime_dsn", f"host=db dbname=palimpsest user=palimpsest password={runtime_password}",0o444)
    os.chown(artifacts,10001,10001)
    os.chmod(artifacts,0o700)
    for path in (admin,app,artifacts):
        _fsync_directory(path)
    print("Palimpsest volumes initialized; credential values withheld.")


if __name__ == "__main__":
    main()
