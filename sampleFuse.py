#!/usr/bin/env python
"""
This code will metion all files in the primaryFS and fallbackFS

Commands:

python3 ./sampleFuse.py ./primaryFS/ ./fallbackFS/ ./mountPoint/
./fallbackFS/

Usage: with another terminal as root you can list the directory
"""


import os
import sys
import errno

from fuse import FUSE, FuseOSError, Operations


class Passthrough(Operations):
    def __init__(self, root, fallbackPath=None):
        self.root = root
        self.fallbackPath = fallbackPath

    # Helpers
    # =======

    def _full_path(self, partial, useFallBack=False):
            if partial.startswith("/"):
                partial = partial[1:]

            # Find out the real path. If has been requesetd for a fallback path,
            # use it
            path = primaryPath = os.path.join(
                self.fallbackPath if useFallBack else self.root, partial)

            # If the pah does not exists and we haven't been asked for the fallback path
            # try to look on the fallback filessytem
            if not os.path.exists(primaryPath) and not useFallBack:
                path = fallbackPath = os.path.join(self.fallbackPath, partial)

                # If the path does not exists neither in the fallback fielsysem
                # it's likely to be a write operation, so use the primary
                # filesystem... unless the path to get the file exists in the
                # fallbackFS!
                if not os.path.exists(fallbackPath):
                    # This is probabily a write operation, so prefer to use the
                    # primary path either if the directory of the path exists in the
                    # primary FS or not exists in the fallback FS

                    primaryDir = os.path.dirname(primaryPath)
                    fallbackDir = os.path.dirname(fallbackPath)

                    if os.path.exists(primaryDir) or not os.path.exists(fallbackDir):
                        path = primaryPath

            return path

    # Filesystem methods
    # ==================

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
                                                        'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid', 'st_blocks'))

    def readdir(self, path, fh):
            dirents = ['.', '..']
            full_path = self._full_path(path)
            # print("listing " + full_path)
            if os.path.isdir(full_path):
                dirents.extend(os.listdir(full_path))
            if self.fallbackPath not in full_path:
                full_path = self._full_path(path, useFallBack=True)
                # print("listing_ext " + full_path)
                if os.path.isdir(full_path):
                    dirents.extend(os.listdir(full_path))
            for r in list(set(dirents)):
                yield r


    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
                                                         'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
                                                         'f_frsize', 'f_namemax'))

    def unlink(self, path):
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)


def main(mountpoint, root, fallbackPath=None):
    if fallbackPath:
        FUSE(Passthrough(root, fallbackPath), mountpoint, nothreads=True, foreground=True)
    else:
        FUSE(Passthrough(root), mountpoint, nothreads=True, foreground=True)


if __name__ == '__main__':
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python dfs.py primary_fs_root [fallback_fs_root] mount_point")
        sys.exit(1)

    primary_fs_root = sys.argv[1]
    fallback_fs_root = sys.argv[2] if len(sys.argv) == 4 else None
    mount_point = sys.argv[-1]
    print(fallback_fs_root)
    main(mount_point, primary_fs_root, fallback_fs_root)
