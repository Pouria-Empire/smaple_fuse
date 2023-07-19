import os
import sys
import errno
from libfuse import FUSE, FuseOSError, Operations
import subprocess

class Passthrough(Operations):
    def __init__(self, root, fallbackPath=None, remote_host=None, remote_directory=None, local_mount_point=None):
        self.root = root
        self.fallbackPath = fallbackPath
        self.remote_host = remote_host
        self.remote_directory = remote_directory
        self.local_mount_point = local_mount_point

        if fallbackPath and remote_host and remote_directory and local_mount_point:
            # Mount the remote directory using SSHFS
            mount_command = ['sshfs', f'{self.remote_host}:{self.remote_directory}', self.local_mount_point, '-o', 'nonempty,rw']
            subprocess.run(mount_command, check=True)
            print("Server mounted")

    def __del__(self):
        if self.fallbackPath and self.remote_host and self.remote_directory and self.local_mount_point:
            # Unmount the remote directory
            unmount_command = ['fusermount', '-u', self.local_mount_point]
            subprocess.run(unmount_command, check=True)
            print("Server unmounted")

    def _full_path(self, partial, useFallBack=False):
        if partial.startswith("/"):
            partial = partial[1:]

        # Find out the real path. If it has been requested for a fallback path, use it.
        path = primaryPath = os.path.join(self.root if not useFallBack else self.fallbackPath, partial)

        # If the path does not exist and we haven't been asked for the fallback path, try to look in the fallback filesystem.
        if not os.path.exists(primaryPath) and not useFallBack:
            path = fallbackPath = os.path.join(self.fallbackPath, partial)

            # If the path does not exist in the fallback filesystem, check if it exists in the remote filesystem.
            if not os.path.exists(fallbackPath) and self.remote_host and self.remote_directory and self.local_mount_point:
                remote_full_path = os.path.join(self.local_mount_point, partial)
                if os.path.exists(remote_full_path):
                    path = remote_full_path

        return path

    def readdir(self, path, fh):
        dirents = ['.', '..']
        full_path = self._full_path(path)

        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))

        if self.fallbackPath and self.fallbackPath not in full_path:
            fallback_full_path = self._full_path(path, useFallBack=True)
            if os.path.isdir(fallback_full_path):
                dirents.extend(os.listdir(fallback_full_path))

        if self.remote_host and self.remote_directory and self.local_mount_point:
            if path == '/':
                remote_full_path = self.local_mount_point
            else:
                remote_full_path = os.path.join(self.local_mount_point, path)
            print(path)
            print(remote_full_path)
            if os.path.isdir(remote_full_path):
                dirents.extend(os.listdir(remote_full_path))

        for r in set(dirents):
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                                                        'st_gid', 'st_mode', 'st_mtime',
                                                        'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)
        dirents = ['.', '..'] + os.listdir(full_path)
        for r in dirents:
            yield r

    def read(self, path, length, offset, fh):
        full_path = self._full_path(path)
        with open(full_path, 'rb') as f:
            os.lseek(fh, offset, os.SEEK_SET)
            return f.read(length)

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def write(self, path, buf, offset, fh):
        full_path = self._full_path(path)
        with open(full_path, 'rb+') as f:
            os.lseek(fh, offset, os.SEEK_SET)
            return f.write(buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def unlink(self, path):
        full_path = self._full_path(path)
        return os.unlink(full_path)

    def utimens(self, path, times=None):
        full_path = self._full_path(path)
        return os.utime(full_path, times)


def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <mountpoint> <root> [--fallback <fallbackPath> --remote <remote_host:remote_directory> --local <local_mount_point>]")
        sys.exit(1)

    mountpoint = sys.argv[1]
    root = sys.argv[2]

    fallbackPath = None
    remote_host = None
    remote_directory = None
    local_mount_point = None

    # Check for optional arguments
    if "--fallback" in sys.argv:
        fallbackPath = sys.argv[sys.argv.index("--fallback") + 1]
    if "--remote" in sys.argv:
        remote = sys.argv[sys.argv.index("--remote") + 1]
        remote_host, remote_directory = remote.split(":")
    if "--local" in sys.argv:
        local_mount_point = sys.argv[sys.argv.index("--local") + 1]

    if fallbackPath and remote_host and remote_directory and local_mount_point:
        FUSE(Passthrough(root, fallbackPath, remote_host, remote_directory, local_mount_point), mountpoint, nothreads=True, foreground=True)
    elif fallbackPath:
        FUSE(Passthrough(root, fallbackPath), mountpoint, nothreads=True, foreground=True)
    else:
        FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)


if __name__ == '__main__':
    main()