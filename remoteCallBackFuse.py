import subprocess
import os
import sys
import errno

from fuse import FUSE, FuseOSError, Operations



class Passthrough(Operations):
    def __init__(self, root, fallbackPath=None, remote_host=None, remote_directory=None, local_mount_point=None):
        self.root = root
        self.fallbackPath = fallbackPath
        self.remote_host = remote_host
        self.remote_directory = remote_directory
        self.local_mount_point = local_mount_point

        if fallbackPath and remote_host and remote_directory and local_mount_point:
            # Mount the remote directory using SSHFS
            mount_command = ['sshfs', f'{self.remote_host}:{self.remote_directory}', self.local_mount_point, '-o', 'nonempty']
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



    def access(self, path, mode):
        print("accessing the files")
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

        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))

        if self.fallbackPath and self.fallbackPath not in full_path:
            fallback_full_path = self._full_path(path, useFallBack=True)
            if os.path.isdir(fallback_full_path):
                dirents.extend(os.listdir(fallback_full_path))

        if self.remote_host and self.remote_directory and self.local_mount_point:
            remote_full_path = self.local_mount_point
            print(remote_full_path)
            if os.path.isdir(remote_full_path):
                dirents.extend(os.listdir(remote_full_path))

        for r in set(dirents):
            yield r


    def readlink(self, path):
        print("Reading the link")
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
        print("Opening")
        full_path = self._full_path(path)
        
        if self.remote_host and self.remote_directory and self.local_mount_point:
            remote_full_path = os.path.join(self.local_mount_point, path)
            if os.path.exists(remote_full_path):
                return os.open(remote_full_path, flags)

        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print("creating")
        full_path = self._full_path(path)
        
        if self.remote_host and self.remote_directory and self.local_mount_point:
            remote_full_path = os.path.join(self.local_mount_point, path)
            return os.open(remote_full_path, os.O_WRONLY | os.O_CREAT, mode)

        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
    
    def read(self, path, length, offset, fh):
        print("reading function")
        os.lseek(fh, offset, os.SEEK_SET)

        if self.remote_host and self.remote_directory and self.local_mount_point:
            remote_full_path = os.path.join(self.local_mount_point, path)
            print("remote accessing file")
            print(remote_full_path)
            if os.path.exists(remote_full_path):
                with open(remote_full_path, 'rb') as f:
                    f.seek(offset)
                    return f.read(length)

        return os.read(fh, length)


    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        
        if self.remote_host and self.remote_directory and self.local_mount_point:
            return os.write(fh, buf)

        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        
        if self.remote_host and self.remote_directory and self.local_mount_point:
            remote_full_path = os.path.join(self.local_mount_point, path)
            with open(remote_full_path, 'r+') as f:
                f.truncate(length)
            return 0

        with open(full_path, 'r+') as f:
            f.truncate(length)
        return 0


    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)
    

# python3 remoteCallBackFuse.py ./mountPoint ./primaryFS --fallback ./fallbackFS --remote 188.40.23.247:/root/sshfs --local ./remote


import sys

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