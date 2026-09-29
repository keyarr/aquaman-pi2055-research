/*
 * ghostlock_reachability.c — Fase 10, probe benigno.
 *
 * Testa APENAS que o caminho FUTEX_WAIT_REQUEUE_PI / FUTEX_CMP_REQUEUE_PI
 * existe e responde como o 4.9.113 stock deveria responder a parametros
 * invalidos. Nao cria par PI, nao tenta deadlock, nao toca em credenciais,
 * nao escreve em ponteiro de kernel, nao faz reclaim.
 *
 * Risco: desprezivel. Todas as chamadas usam uaddrs invalidos ou iguais e
 * devem retornar -EINVAL antes de qualquer manipulacao de waiter. O unico
 * teste funcional (LOCK_PI/UNLOCK_PI no proprio futex privado) eh uso
 * normal de PI mutex, sem requeue.
 *
 * Build (NDK, ARM64, Android 9+):
 *   $NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang \
 *     -O2 -Wall -Wextra -fPIE -pie ghostlock_reachability.c -o ghostlock_reachability
 * Run:
 *   adb push ghostlock_reachability /data/local/tmp/
 *   adb shell /data/local/tmp/ghostlock_reachability
 *
 * Saida esperada num kernel 4.9.113 com PI compilado:
 *   7 checks, 7 PASS. Qualquer FAIL vira INCOMPATIVEL no relatorio.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#ifndef __NR_futex
#define __NR_futex 98
#endif
#ifndef FUTEX_WAIT_REQUEUE_PI
#define FUTEX_WAIT_REQUEUE_PI 11
#define FUTEX_CMP_REQUEUE_PI 12
#define FUTEX_LOCK_PI 6
#define FUTEX_UNLOCK_PI 7
#define FUTEX_PRIVATE_FLAG 128
#endif

static int g_pass = 0, g_fail = 0;

static long xfutex(void *u1, int op, uint32_t val, void *timeout, void *u2,
                   uint32_t val3) {
    return syscall(__NR_futex, u1, op, val, timeout, u2, val3);
}

static void check(const char *name, int expect_errno, long ret) {
    int got = (ret == -1) ? errno : 0;
    if (ret == -1 && got == expect_errno) {
        printf("[PASS] %-48s errno=%d (%s)\n", name, got, strerror(got));
        g_pass++;
    } else {
        printf("[FAIL] %-48s ret=%ld errno=%d want errno=%d\n", name, ret,
               got, expect_errno);
        g_fail++;
    }
}

int main(void) {
    struct utsname u;
    uint32_t a = 0, b = 0;

    if (!uname(&u))
        printf("[info] kernel %s %s %s\n", u.release, u.version, u.machine);

    /* 1-2: uaddr1 == uaddr2 sempre retorna -EINVAL antes de tocar em waiter
     * (futex.c: uaddr check no inicio de futex_wait_requeue_pi e
     * futex_requeue requeue_pi). Se o comando nao existisse, veriamos
     * -ENOSYS. */
    check("WAIT_REQUEUE_PI same uaddr -> EINVAL",
          EINVAL, xfutex(&a, FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         0, NULL, &a, 0));
    check("CMP_REQUEUE_PI same uaddr -> EINVAL",
          EINVAL, xfutex(&a, FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)1, &a, 0));

    /* 3: CMP_REQUEUE_PI com cmpval divergente deve retornar -EAGAIN apos
     * resolver as keys (prova que get_futex_key + comparacao funcionam).
     * Mapeamento: val=nr_wake(1), timeout=nr_requeue(1), uaddr2, val3=cmpval.
     * a=0, cmpval=0xdeadbeef -> mismatch -> EAGAIN. */
    a = 0;
    check("CMP_REQUEUE_PI bad cmpval -> EAGAIN",
          EAGAIN, xfutex(&a, FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)1, &b, 0xdeadbeef));

    /* 4: endereco de usuario invalido deve retornar -EFAULT, nao crash. */
    check("CMP_REQUEUE_PI bad uaddr -> EFAULT",
          EFAULT, xfutex((void *)0xdead0000,
                         FUTEX_CMP_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                         1, (void *)(uintptr_t)0, &b, 0));

    /* 5-6: bitset zero em WAIT_REQUEUE_PI retorna -EINVAL (prova que o
     * handler entrou no parsing de argumentos). Nao ha bitset via
     * syscall direta sem wrapper, entao este teste usa timeout NULL +
     * val que nao casa: o caminho esperado eh EAGAIN/EINVAL, nunca
     * bloqueio. Timeout zero evita qualquer espera. */
    {
        struct timespec ts = {0, 0};
        long r = xfutex(&a, FUTEX_WAIT_REQUEUE_PI | FUTEX_PRIVATE_FLAG,
                        0x12345678, &ts, &b, 0);
        /* val nao casa com *uaddr (0): futex_wait_setup retorna -EAGAIN. */
        check("WAIT_REQUEUE_PI val mismatch -> EAGAIN",
              EAGAIN, r);
    }

    /* 7-8: PI funcional basico, sem requeue: LOCK_PI num futex zerado
     * privado adquire na hora (ret 0), UNLOCK_PI libera (ret 0). So prova
     * que rt_mutex PI esta operacional para o chamador. */
    {
        uint32_t pi = 0;
        long r1 = xfutex(&pi, FUTEX_LOCK_PI | FUTEX_PRIVATE_FLAG, 0,
                         NULL, NULL, 0);
        if (r1 == 0) {
            printf("[PASS] %-48s ret=0\n", "LOCK_PI self acquire");
            g_pass++;
        } else {
            printf("[FAIL] %-48s ret=%ld errno=%d\n",
                   "LOCK_PI self acquire", r1, errno);
            g_fail++;
        }
        long r2 = xfutex(&pi, FUTEX_UNLOCK_PI | FUTEX_PRIVATE_FLAG, 0,
                         NULL, NULL, 0);
        if (r2 == 0) {
            printf("[PASS] %-48s ret=0\n", "UNLOCK_PI self release");
            g_pass++;
        } else {
            printf("[FAIL] %-48s ret=%ld errno=%d\n",
                   "UNLOCK_PI self release", r2, errno);
            g_fail++;
        }
    }

    printf("[summary] pass=%d fail=%d\n", g_pass, g_fail);
    return g_fail ? 1 : 0;
}
