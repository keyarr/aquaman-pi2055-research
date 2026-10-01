/* ghostlock_emit_probe.c - read-only emit probes for C1/C2/C3 (no trigger, no write).
 *
 * P0 READY / P1 OPEN / P2 QUERY / P3 CAPTURE / P4 CLOSE / P5 VERIFY
 * Isolated from GhostLock: no futex trigger, no stamp, no fake, no memory touch
 * beyond ordinary open/ioctl/close on the candidate fd itself.
 *
 * C1 binder:  BINDER_VERSION + BINDER_GET_NODE_DEBUG_INFO(ptr=0)
 * C2 ashmem:  ASHMEM_GET_SIZE + ASHMEM_GET_NAME (fresh open, no SET_SIZE/SET_NAME)
 * C3 ion:     ION_IOC_HEAP_QUERY cnt=0, then with buffer for up to 16 heaps
 *
 * is_kptr(): VA39 PAGE_OFFSET heuristic (top 16 bits set). A hit does NOT
 * declare a leak; FASE 13 requires field/instruction/copy-site identification.
 *
 * Build (NDK r29, ARM64, API 28):
 *   aarch64-linux-android28-clang -O2 -Wall -static ghostlock_emit_probe.c -o ghostlock_emit_probe
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

static int is_kptr(uint64_t v) {
    return (v >> 48) == 0xffff;
}

static int is_ptr_like(uint64_t v) {
    if (v == 0) return 0;
    if (is_kptr(v)) return 1;
    if ((v & 0xfff) == 0) return 0; /* aligned non-kernel: weak signal only */
    return 0;
}

/* ---- binder (uapi/android/binder.h, arm64: protocol 8) ---- */
struct binder_version {
    int32_t protocol_version;
};
#define BINDER_VERSION _IOWR('b', 9, struct binder_version)
struct binder_node_debug_info {
    uint64_t ptr;
    uint64_t cookie;
    uint32_t has_strong_ref;
    uint32_t has_weak_ref;
};
#define BINDER_GET_NODE_DEBUG_INFO _IOWR('b', 11, struct binder_node_debug_info)

/* ---- ashmem (staging/android/uapi/ashmem.h: __ASHMEMIOC=0x77, NOT 'a') ---- */
#define ASHMEM_GET_NAME _IOR(0x77, 2, char[256])
#define ASHMEM_GET_SIZE _IO(0x77, 4)

/* ---- ion (staging/android/uapi/ion.h) ---- */
#define MAX_HEAP_NAME 32
struct ion_heap_data {
    char name[MAX_HEAP_NAME];
    uint32_t type;
    uint32_t heap_id;
    uint32_t reserved0;
    uint32_t reserved1;
    uint32_t reserved2;
};
struct ion_heap_query {
    uint32_t cnt;
    uint32_t reserved0;
    uint64_t heaps;
    uint32_t reserved1;
    uint32_t reserved2;
};
#define ION_IOC_HEAP_QUERY _IOWR('I', 8, struct ion_heap_query)

static int probe_binder(void) {
    int fd;
    printf("P0 READY candidate=C1 dev=/dev/binder (read-only, no trigger)\n");
    errno = 0;
    fd = open("/dev/binder", O_RDONLY | O_NONBLOCK);
    printf("P1 OPEN fd=%d errno=%d (%s)\n", fd, errno, strerror(errno));
    if (fd < 0) {
        printf("P5 VERIFY C1 OPEN_FAIL (unreachable from shell)\n");
        return 1;
    }
    {
        struct binder_version v;
        memset(&v, 0, sizeof(v));
        errno = 0;
        int r = ioctl(fd, BINDER_VERSION, &v);
        printf("P2 QUERY BINDER_VERSION rc=%d errno=%d (%s) protocol=%d kptr=%d\n",
               r, errno, strerror(errno), v.protocol_version,
               is_kptr((uint64_t)(uint32_t)v.protocol_version));
    }
    {
        struct binder_node_debug_info info;
        memset(&info, 0, sizeof(info));
        info.ptr = 0; /* first node */
        errno = 0;
        int r = ioctl(fd, BINDER_GET_NODE_DEBUG_INFO, &info);
        printf("P3 CAPTURE NODE_DEBUG rc=%d errno=%d (%s)\n", r, errno, strerror(errno));
        printf("P3 CAPTURE ptr=%#llx cookie=%#llx strong=%u weak=%u\n",
               (unsigned long long)info.ptr, (unsigned long long)info.cookie,
               info.has_strong_ref, info.has_weak_ref);
        printf("P5 VERIFY C1 ptr_kptr=%d cookie_kptr=%d ptr_like=%d (expect 0/0/0 on fresh fd: USER_ECHO zeros)\n",
               is_kptr(info.ptr), is_kptr(info.cookie), is_ptr_like(info.ptr));
    }
    /* repeat once for stability (FASE 12) */
    {
        struct binder_node_debug_info info2;
        memset(&info2, 0, sizeof(info2));
        errno = 0;
        int r = ioctl(fd, BINDER_GET_NODE_DEBUG_INFO, &info2);
        printf("P3 CAPTURE repeat rc=%d ptr=%#llx cookie=%#llx (stability check)\n",
               r, (unsigned long long)info2.ptr, (unsigned long long)info2.cookie);
    }
    close(fd);
    printf("P4 CLOSE fd closed\n");
    return 0;
}

static int probe_ashmem(void) {
    int fd;
    printf("P0 READY candidate=C2 dev=/dev/ashmem (read-only, no trigger)\n");
    errno = 0;
    fd = open("/dev/ashmem", O_RDONLY | O_NONBLOCK);
    printf("P1 OPEN fd=%d errno=%d (%s)\n", fd, errno, strerror(errno));
    if (fd < 0) {
        printf("P5 VERIFY C2 OPEN_FAIL\n");
        return 1;
    }
    {
        errno = 0;
        long sz = ioctl(fd, ASHMEM_GET_SIZE);
        printf("P2 QUERY ASHMEM_GET_SIZE rc=%ld errno=%d (%s) kptr=%d (expect 0, scalar)\n",
               sz, errno, strerror(errno), sz < 0 ? 0 : is_kptr((uint64_t)sz));
    }
    {
        char name[256];
        memset(name, 0, sizeof(name));
        errno = 0;
        int r = ioctl(fd, ASHMEM_GET_NAME, name);
        name[sizeof(name) - 1] = 0;
        printf("P3 CAPTURE ASHMEM_GET_NAME rc=%d errno=%d (%s) name=\"%.32s\" kptr=%d (expect USER_ECHO dev/ashmem)\n",
               r, errno, strerror(errno), name, 0);
    }
    close(fd);
    printf("P4 CLOSE fd closed\n");
    printf("P5 VERIFY C2 scalar+user-string only (no kernel pointer by construction)\n");
    return 0;
}

static int probe_ion(void) {
    int fd;
    printf("P0 READY candidate=C3 dev=/dev/ion (read-only, no trigger)\n");
    errno = 0;
    fd = open("/dev/ion", O_RDONLY | O_NONBLOCK);
    printf("P1 OPEN fd=%d errno=%d (%s)\n", fd, errno, strerror(errno));
    if (fd < 0) {
        printf("P5 VERIFY C3 OPEN_FAIL\n");
        return 1;
    }
    {
        struct ion_heap_query q;
        memset(&q, 0, sizeof(q));
        q.cnt = 0;
        q.heaps = 0;
        errno = 0;
        int r = ioctl(fd, ION_IOC_HEAP_QUERY, &q);
        printf("P2 QUERY HEAP_QUERY_CNT0 rc=%d errno=%d (%s) cnt=%u kptr=%d (expect count scalar)\n",
               r, errno, strerror(errno), q.cnt, 0);
        if (r == 0 && q.cnt > 0 && q.cnt <= 16) {
            struct ion_heap_data buf[16];
            uint32_t n = q.cnt > 16 ? 16 : q.cnt;
            memset(buf, 0, sizeof(buf));
            q.cnt = n;
            q.heaps = (uint64_t)(uintptr_t)buf;
            errno = 0;
            r = ioctl(fd, ION_IOC_HEAP_QUERY, &q);
            printf("P3 CAPTURE HEAP_QUERY_BUF rc=%d errno=%d (%s) cnt=%u\n",
                   r, errno, strerror(errno), q.cnt);
            for (uint32_t i = 0; i < n && i < q.cnt; i++) {
                char nm[33];
                memcpy(nm, buf[i].name, 32);
                nm[32] = 0;
                printf("P3 CAPTURE heap[%u] name=\"%.32s\" type=%u id=%u kptr=%d\n",
                       i, nm, buf[i].type, buf[i].heap_id, 0);
            }
            printf("P5 VERIFY C3 name/type/id only (INDEX+SCALAR, no kernel VA by construction)\n");
        } else {
            printf("P3 CAPTURE skipped buffer query (cnt=%u rc=%d)\n", q.cnt, r);
            printf("P5 VERIFY C3 count-only (scalar)\n");
        }
    }
    close(fd);
    printf("P4 CLOSE fd closed\n");
    return 0;
}

int main(int argc, char **argv) {
    const char *which = argc > 1 ? argv[1] : "all";
    setbuf(stdout, 0);
    if (!strcmp(which, "binder") || !strcmp(which, "all"))
        probe_binder();
    if (!strcmp(which, "ashmem") || !strcmp(which, "all"))
        probe_ashmem();
    if (!strcmp(which, "ion") || !strcmp(which, "all"))
        probe_ion();
    if (strcmp(which, "binder") && strcmp(which, "ashmem") &&
        strcmp(which, "ion") && strcmp(which, "all")) {
        printf("usage: %s [binder|ashmem|ion|all]\n", argv[0]);
        return 2;
    }
    printf("P6 RESULT=EMIT_PROBE_DONE which=%s (read-only, no trigger, no write)\n", which);
    return 0;
}
