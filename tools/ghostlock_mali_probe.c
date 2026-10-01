/* ghostlock_mali_probe.c - read-only Mali Utgard version/info queries.
 * Max 3 candidates, open/version/query/close only. No submit/alloc/map.
 * Cmds decoded from out/vendor/modules/mali.ko mali_ioctl dispatch (OFFLINE).
 * If any output word has top16==0xffff -> STOP, report, do not continue.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int is_kptr(uint64_t v) { return (v >> 48) == 0xffff; }

int main(void) {
    int fd;
    setbuf(stdout, 0);
    printf("P0 READY dev=/dev/mali (read-only version/info, no trigger)\n");
    fd = open("/dev/mali", O_RDONLY | O_NONBLOCK);
    printf("P1 OPEN fd=%d errno=%d (%s)\n", fd, errno, strerror(errno));
    if (fd < 0) { printf("P5 VERIFY OPEN_FAIL\n"); return 1; }

    /* C-M1: GET_API_VERSION_V2 0xc0108203 size16 -> version u32s */
    {
        uint8_t buf[16];
        memset(buf, 0xaa, sizeof(buf));
        errno = 0;
        int r = ioctl(fd, 0xc0108203u, buf);
        printf("P2 QUERY API_V2 rc=%d errno=%d (%s)\n", r, errno, strerror(errno));
        printf("P3 CAPTURE api_v2 bytes:");
        for (int i = 0; i < 16; i++) printf(" %02x", buf[i]);
        printf("\n");
        uint32_t w0, w1;
        memcpy(&w0, buf + 8, 4); memcpy(&w1, buf + 12, 4);
        uint64_t q; memcpy(&q, buf + 8, 8);
        printf("P5 VERIFY M1 w8=%u w12=%u q64=%#llx kptr=%d (expect 900/900, kptr 0)\n",
               w0, w1, (unsigned long long)q, is_kptr(q));
        if (is_kptr(q)) { printf("P6 STOP KPTR OBSERVED M1\n"); close(fd); return 0; }
    }
    /* C-M2: GET_API_VERSION 0xc0048203 size4 -> version u32 */
    {
        uint8_t buf[16];
        memset(buf, 0xaa, sizeof(buf));
        errno = 0;
        int r = ioctl(fd, 0xc0048203u, buf);
        printf("P2 QUERY API_V1 rc=%d errno=%d (%s)\n", r, errno, strerror(errno));
        printf("P3 CAPTURE api_v1 bytes:");
        for (int i = 0; i < 16; i++) printf(" %02x", buf[i]);
        printf("\n");
        uint32_t w;
        memcpy(&w, buf + 4, 4);
        uint64_t q = 0; memcpy(&q, buf, 8);
        uint64_t q2 = 0; memcpy(&q2, buf + 8, 8);
        printf("P5 VERIFY M2 w4=%u q0=%#llx q8=%#llx kptr=%d/%d (expect 900, kptr 0)\n",
               w, (unsigned long long)q, (unsigned long long)q2,
               is_kptr(q), is_kptr(q2));
        if (is_kptr(q) || is_kptr(q2)) { printf("P6 STOP KPTR OBSERVED M2\n"); close(fd); return 0; }
    }
    /* C-M3: GP_GET_CORE_VERSION 0x80108502 size16 _IOR -> u32 version */
    {
        uint8_t buf[16];
        memset(buf, 0xaa, sizeof(buf));
        errno = 0;
        int r = ioctl(fd, 0x80108502u, buf);
        printf("P2 QUERY GP_CORE_VER rc=%d errno=%d (%s)\n", r, errno, strerror(errno));
        printf("P3 CAPTURE gp_core bytes:");
        for (int i = 0; i < 16; i++) printf(" %02x", buf[i]);
        printf("\n");
        uint32_t w;
        memcpy(&w, buf + 8, 4);
        uint64_t q; memcpy(&q, buf + 8, 8);
        printf("P5 VERIFY M3 w8=%u q64=%#llx kptr=%d (expect small scalar, kptr 0)\n",
               w, (unsigned long long)q, is_kptr(q));
        if (is_kptr(q)) { printf("P6 STOP KPTR OBSERVED M3\n"); close(fd); return 0; }
    }
    close(fd);
    printf("P4 CLOSE fd closed\n");
    printf("P6 RESULT=MALI_PROBE_DONE (read-only, no trigger, no write)\n");
    return 0;
}
