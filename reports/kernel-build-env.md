# kernel-build-env — ambiente de build 4.9.113 reproduzível

## árvores (somente leitura, nenhuma modificada)

| papel | caminho | versão | HEAD |
|---|---|---|---|
| base ancestral | `/tmp/kernel-src/linux-amlogic` | 4.9.113 | 3d4ab79e 2019-06-27 |
| ref oficial Xiaomi (outro aparelho) | `/tmp/kernel-src/MiTV_OpenSource` (branch dangal-p-oss) | 4.9.113 | 2019-07-11 |
| toolchain | `/tmp/kernel-src/MiTV_OpenSource/cross_compile_tool` | Linaro 6.3-2017.02, gcc 6.3.1 20170109 | — |

o gcc 6.3.1 é exatamente o da string de build do stock
(`jenkins@c5-mitv-cm-build06.bj`, gcc Linaro 6.3-2017.02). sem toolchain
global instalada; `CROSS_COMPILE` aponta para o binário vendored. `dtc` 1.7.2
do sistema só para inspeção; o build usa o `scripts/dtc` da árvore.

## objdir (fora da árvore)

`./build-aq/` (gitignored). build com `O=`, fonte nunca tocada:

```sh
make ARCH=arm64 \
  CROSS_COMPILE=/tmp/kernel-src/MiTV_OpenSource/cross_compile_tool/bin/aarch64-linux-gnu- \
  HOSTCFLAGS="-fcommon" \
  O=$PWD/build-aq -C /tmp/kernel-src/linux-amlogic meson64_defconfig
make ARCH=arm64 CROSS_COMPILE=... HOSTCFLAGS="-fcommon" O=$PWD/build-aq \
  -C /tmp/kernel-src/linux-amlogic Image -j$(nproc)
```

## dois fixes de ambiente (fora da árvore kernel, documentados)

1. `HOSTCFLAGS="-fcommon"`: dtc do 4.9 não linka com host gcc ≥ 10
   (`multiple definition of yylloc`). flag de linha de comando, zero patch.
2. symlink criado no toolchain vendored (cópia de pesquisa, não upstream):
   `cross_compile_tool/libexec/gcc/aarch64-linux-gnu/6.3.1/liblto_plugin.so
   -> liblto_plugin.so.0.0.0`. o driver gcc procura `liblto_plugin.so` no
   link do vdso e o arquivo veio sem o symlink. sem isso:
   `fatal error: -fuse-linker-plugin, but liblto_plugin.so not found`.

## resultado

`build-aq/arch/arm64/boot/Image`, 26 MB, `4.9.113`, ELF via Linaro 6.3.1,
header ARM64 válido (`magic 0x644d5241 @0x38`, `text_offset 0x1080000`,
`image_size 0x1bdf000`). `EXIT=0` com 2 section mismatches (warning padrão
desse vendor drop, `VIDEO`/`USB`, semzóio por enquanto).

## armadilhas

- `/tmp` é tmpfs (7.7 GB, 4.4 livres no teste): objdir de ~3 GB estourou o
  disco no meio do link (`final link failed: No space left`). objdir fica
  em `/home`, não em `/tmp`.
- `.config` local tem 2 desvios do `meson64_defconfig` expandido (detalhes no
  `kernel-baseline.md`): `VDEC_VP9=n` (quebrado no tip, `gvs` undeclared) e
  `VIDEOSYNC=y` (video_sink referencia o símbolo sem guarda; aquaman não tem
  nenhum dos dois — layout de Kconfig da mídia é diferente na árvore Xiaomi).
