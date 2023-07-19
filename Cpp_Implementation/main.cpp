#define FUSE_USE_VERSION 31

#include <fuse.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <cstdlib>
#include <limits.h>
#include <dirent.h>

static const char *root;
static const char *fallbackPath;
static const char *remoteHost;
static const char *remoteDirectory;
static const char *localMountPoint;

static char *get_full_path(const char *path, bool useFallback = false) {
    char *full_path = (char *)malloc(PATH_MAX);
    if (full_path == NULL) {
        return NULL;
    }

    if (path[0] == '/') {
        path++;
    }

    if (!useFallback) {
        snprintf(full_path, PATH_MAX, "%s/%s", root, path);
        if (access(full_path, F_OK) == 0) {
            return full_path;
        }
    }

    if (fallbackPath != NULL) {
        snprintf(full_path, PATH_MAX, "%s/%s", fallbackPath, path);
        if (access(full_path, F_OK) == 0) {
            return full_path;
        }
    }

    if (remoteHost != NULL && remoteDirectory != NULL && localMountPoint != NULL) {
        snprintf(full_path, PATH_MAX, "%s/%s/%s", localMountPoint, remoteDirectory, path);
        if (access(full_path, F_OK) == 0) {
            return full_path;
        }
    }

    free(full_path);
    return NULL;
}

static int passthrough_getattr(const char *path, struct stat *stbuf) {
    int res;
    char *full_path = get_full_path(path);
    if (full_path == NULL) {
        return -ENOENT;
    }

    res = lstat(full_path, stbuf);
    free(full_path);

    if (res == -1) {
        return -errno;
    }

    return 0;
}

static int passthrough_readdir(const char *path, void *buf, fuse_fill_dir_t filler, off_t offset, struct fuse_file_info *fi) {
    char *full_path = get_full_path(path);
    if (full_path == NULL) {
        return -ENOENT;
    }

    DIR *dp;
    struct dirent *de;

    dp = opendir(full_path);
    if (dp == NULL) {
        free(full_path);
        return -errno;
    }

    while ((de = readdir(dp)) != NULL) {
        struct stat st;
        memset(&st, 0, sizeof(st));
        st.st_ino = de->d_ino;
        st.st_mode = de->d_type << 12;
        if (filler(buf, de->d_name, &st, 0)) {
            break;
        }
    }

    closedir(dp);
    free(full_path);
    return 0;
}

static int passthrough_read(const char *path, char *buf, size_t size, off_t offset, struct fuse_file_info *fi) {
    int fd;
    int res;
    char *full_path = get_full_path(path);
    if (full_path == NULL) {
        return -ENOENT;
    }

    fd = open(full_path, O_RDONLY);
    if (fd == -1) {
        free(full_path);
        return -errno;
    }

    res = pread(fd, buf, size, offset);
    if (res == -1) {
        res = -errno;
    }

    close(fd);
    free(full_path);
    return res;
}

static int passthrough_write(const char *path, const char *buf, size_t size, off_t offset, struct fuse_file_info *fi) {
    int fd;
    int res;
    char *full_path = get_full_path(path);
    if (full_path == NULL) {
        return -ENOENT;
    }

    fd = open(full_path, O_WRONLY);
    if (fd == -1) {
        free(full_path);
        return -errno;
    }

    res = pwrite(fd, buf, size, offset);
    if (res == -1) {
        res = -errno;
    }

    close(fd);
    free(full_path);
    return res;
}

static int passthrough_mkdir(const char *path, mode_t mode) {
    int res;
    char *full_path = get_full_path(path);
    if (full_path == NULL) {
        return -ENOENT;
    }

    res = mkdir(full_path, mode);
    free(full_path);

    if (res == -1) {
        return -errno;
    }

    return 0;
}

// Add other functions (e.g., passthrough_create, passthrough_unlink, passthrough_truncate) as needed

static struct fuse_operations passthrough_operations = {
    .getattr = passthrough_getattr,
    .readdir = passthrough_readdir,
    .read = passthrough_read,
    .write = passthrough_write,
    .mkdir = passthrough_mkdir,
    // Add other function pointers here
};

int main(int argc, char *argv[]) {
    if (argc < 3) {
        printf("Usage: %s <mountpoint> <root> [--fallback <fallbackPath> --remote <remote_host:remote_directory> --local <local_mount_point>]\n", argv[0]);
        return 1;
    }

    const char *mountpoint = argv[1];
    root = argv[2];

    fallbackPath = NULL;
    remoteHost = NULL;
    remoteDirectory = NULL;
    localMountPoint = NULL;

    // Check for optional arguments
    for (int i = 3; i < argc; i++) {
        if (strcmp(argv[i], "--fallback") == 0 && i + 1 < argc) {
            fallbackPath = argv[i + 1];
            i++;
        } else if (strcmp(argv[i], "--remote") == 0 && i + 1 < argc) {
            const char *remote = argv[i + 1];
            remoteHost = strtok((char *)remote, ":");
            remoteDirectory = strtok(NULL, ":");
            i++;
        } else if (strcmp(argv[i], "--local") == 0 && i + 1 < argc) {
            localMountPoint = argv[i + 1];
            i++;
        }
    }

    return fuse_main(argc, argv, &passthrough_operations, NULL);
}
