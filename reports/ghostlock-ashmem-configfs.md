# GhostLock ashmem + configfs no aquaman (Fase 6 + Fase 7)

## Compilado (aquaman-config) — CONFIRMADO

- CONFIG_ASHMEM=y (staging android)
- CONFIG_CONFIGFS_FS=y
- CONFIG_UNIX=y, CONFIG_UNIX_DIAG=y
- CONFIG_NET=y, CONFIG_IPV6=y (necessario ao stack stamper do hazel)
- PIPE: implicito (sempre presente; usado como plano B)

## Runtime (shell nao-privilegiado) — CONFIRMADO 2026-09-29 via adb

- /dev/ashmem: crw-rw-rw- root root 10,61. Shell abre. CONFIRMADO.
- /proc/filesystems lista configfs (nodev configfs). CONFIRMADO.
- configfs montado em /sys/kernel/config e /config (rw). CONFIRMADO.
- `ls /sys/kernel/config`: Permission denied (listagem negada; criar
  subdir proprio ainda nao testado — proximo teste read-only: tentar
  mkdir em /config + dmesg? mkdir em configfs eh escrita no fs, nao no
  kernel sensivel; risco baixo mas fica para o passo seguinte).
- /proc/cmdline e /sys/fs/pstore: Permission denied para shell.
  Sem pstore legivel, diagnostico post-mortem de panic fica limitado a
  observacao via adb (morreu = reboot/hang) e bootreason se exposto.
  Risco registrado, sem UART continua valendo power cycle fisico.

## Ponto fragil: dentry no caminho configfs via fd ashmem

O hazel reaproveita o proprio fd /dev/ashmem com f_op trocado para o
fake fops (.read/.write = configfs_read/write_file). Nao precisa de
mount configfs. Mas configfs_read_file chama to_attr(dentry) e
to_item(parent) sobre file->f_path.dentry — com um dentry de /dev/ashmem
isso, em tese, falha. Ler fs/configfs/file.c:69-130 antes de assumir: o
hazel passou em hw-test, entao o caminho tolera na pratica, mas eh o
ponto mais fragil do port e precisa de leitura atenta contra o dentry
real do aquaman.

## Implementacao ashmem na arvore — CONFIRMADO (drivers/staging/android)

- struct ashmem_area { name[ASHMEM_FULL_NAME_LEN]; unpinned_list;
  file; size; prot_mask } (ashmem.c:54-60). ASHMEM_FULL_NAME_LEN: ler
  ashmem.h — o blob do hazel assume prefixo "/dev/ashmem/" (11 chars,
  ASHMEM_NAME_PREFIX_LEN) como primeira word do area. Se o LEN do 4.9
  Amlogic for igual ao upstream, o truque do count gigante se mantem;
  se vendor mudou o nome, quebra.
- ashmem_fops + ashmem_misc (.fops = &ashmem_fops, minor MISC_DYNAMIC)
  + misc_register (linhas 823-862). Superficie /dev/ashmem existe se o
  driver fez probe — no Android TV stick, ashmem quase sempre presente
  (usado por SurfaceFlinger/heap). INFERIDO presente, confirmar com ls.
- ASHMEM_SET_NAME via ioctl: copia o nome para area->name. O hazel
  escreve o blob em fatias por causa dos zeros (set_name_zero_at).
  Mecanica ioctl-level, versao-independente. igual.

## Diferenca ARM32 -> ARM64 no blob — INCOMPATIVEL direto

Ver ghostlock-structs-4.9-arm64.md: mutex +0x18 vira +0x20, ponteiros
8 bytes, page/ops deslocados. O payload de 96B do hazel precisa ser
regenerado para LP64. Tambem o fault-write trick (target-1 +
EFAULT cleanup) depende do copy_from_user vendor; o comentario no hazel
diz "vendor ARM copy_from_user walks from high end" — no ARM64 Amlogic
o comportamento pode diferir; testar o primitive em endereco inofensivo
primeiro (ex.: ler de volta o proprio fake fops, como o hazel faz na
etapa "preloaded read slot").

## Alternativa pronta (plano B)

Rota pipe do aresin (pipe_buffer + physmap) nao precisa de
ashmem/configfs. Se /dev/ashmem nao for acessivel ao shell ou o dentry
configfs nao tolerar, migrar para pipe. Ambas as superficies de spray
(AF_UNIX, pipe) existem no aquaman por config.

## Checklist de runtime — EXECUTADO 2026-09-29 (shell uid 2000)

1. ls -l /dev/ashmem -> crw-rw-rw- root root 10,61. OK.
2. /proc/filesystems -> nodev configfs. OK.
3. mount -> configfs em /sys/kernel/config e /config (rw). OK.
   ls /sys/kernel/config -> Permission denied (anotado acima).
4. id shell u:r:shell:s0; getenforce Enforcing; /proc/version 4.9.113
   Linaro gcc 6.3.1 jenkins@c5-mitv-cm-build06.bj. OK.
   getprop: fingerprint Xiaomi/aquaman/aquaman:9/PI/2055:user/release-keys,
   incremental 2055, cpu abi armeabi-v7a (userspace 32-bit, kernel ARM64).
5. /dev/socket nao checado (AF_UNIX provado pelo proprio uso: sockets
   funcionam; gastar um ciclo aqui quando o spray for calibrado).
