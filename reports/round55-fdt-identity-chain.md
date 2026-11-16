# round55 FDT identity chain (offline only, no hardware, 2026-10-02)

Scope: BL33 real `reports/round14-bl33-persist/bl33-37e18000.bin` + stock
`boot.img` header + `artifacts/aquaman.dtb` + `running_config.gz` do round54.
Nenhum boot, nenhum WRITE, nenhum `bootm`, nenhum `imgread`.

Pergunta unica: `fdt_chosen()` modifica o mesmo FDT que `bootm` entrega ao
Linux, e esse FDT e o mesmo apontado em EL1?

Resposta curta: o `fdt` de `fdt_chosen` e provado offline como
`[images+0x100]`, e `x2` no `eret` e provado offline como o mesmo
`[images+0x100]`. A identidade estrutural fecha. O que nao fecha offline e
o valor runtime em tres pontos: `ft_len` no gate, return de `fdt_setprop`,
e se o blob pos-reloc e o mesmo bytes do dump `0x01000000`. Por isso a
divergencia do round53 continua `UNKNOWN` com fronteira estreitada a um
link, nao explicada.

## Executive conclusion

Onde a cadeia diverge: em nenhum ponto estatico encontrado. Todo escritor
BL33 de `/chosen/bootargs` usa a string do env (`env_get`), nenhum literal
BL33 emite `enforcing` ou `normal` para esses dois campos, o kernel roda
com `CONFIG_CMDLINE=""` (bootloader-only), o blob alvo tem espaco livre, e
a entrada do kernel e `eret` com `x2=FDT` (sem SMC no handoff).

O grafo estatico diz que a string do env deveria vencer. O hardware do
round53 diz que o par stock venceu. Como falha em `fdt_chosen` ou gate
`ft_len==0` pendura o boot (`FDT creation failed! hanging...` /
`FDT and ATAGS support not compiled in - hanging`), e o round53 bootou
Android stock em ~15 s, a deducao mais forte e INFERRED, nao PROVEN:
o fixup rodou e retornou 0, logo `fdt_setprop` teve sucesso no blob
`[images+0x100]`. Se isso vale, a divergencia esta depois do `fdt_setprop`
(blob trocado depois) ou fora do BL33 (init/Linux derivando
`ro.boot.*` de outra fonte), nao num `env_get` errado.

Frase defensavel ao fim: sabemos qual FDT `fdt_chosen` modifica
(`[images+0x100]`, pos-reloc) e sabemos qual FDT o EL1 recebe
(`[images+0x100]` via `x2`), e estruturalmente sao o mesmo campo;
nao sabemos o valor runtime de `ft_len`, o return runtime de
`fdt_setprop`, nem se o blob final e byte-identico ao dump RAM.

## Bootm FDT flow

`bootm @ 0x37e24c00` (cmd_tbl idx 6, `OFFLINE_ONLY` rederivado):

```text
bootm @ 0x37e24c00
 -> SMC verify 0x37e24cf0 (aml_sec_boot_check wrapper 0x37e19ea8)   OFFLINE_ONLY
 -> env rebuild "%s %s %s" @ 0x37e24e64 (bootargs + header + verifiedbootstate orange|green) + setenv  PROVEN (strings 0x37ec015c/0x37ec0060/0x37ec0085, disasm 0x37e24dbc..0x37e24e78)
 -> defendkey gate @ 0x37e24e88..0x37e24f54 (recovery/update/factory_reset/upgrade_step==3 only)  OFFLINE_ONLY, nao e o path fastboot
 -> 0x37e5b2f0 (resolve loadaddr -> images*) + 2o SMC @ 0x37e24f90  OFFLINE_ONLY
 -> do_bootm_states @ 0x37e255c8 com x5=global 0x37f723e8, w4=0x70f, x3=images stack  OFFLINE_ONLY
    -> dentro: bootm_find_os / bootm_load_os / dtb_mem_addr init (default 0x1000000) / decrypt-skip tbz w22,#2 @ 0x37e25d0c  OFFLINE_ONLY
    -> boot_selected_os via OS table 0x37eb5658 -> 0x37e21378 (Linux dispatch)  INFERRED (sem `bl`, so via ponteiro; slot 0x37eb5658 contem 0x37e21378, PROVEN por dump)
 -> 0x37e21378 dispatch por flag:
      0x37e2139c bl 0x37e2122c (fixup gate) + 0x37e213b0 bl 0x37e21284 (entry), ou so um dos dois  OFFLINE_ONLY
 -> 0x37e2122c gate: env_get("bootargs") @ 0x37e21244 (resultado descartado) + ldr x0,[x19+0x108]; cbz -> hang; senao bl 0x37e5b800  PROVEN disasm
 -> 0x37e5b800 stage: ldr x0,[images+0x108] (ft_len), ldr x1,[images+0x100] (ft_addr), bl 0x37e5bd08 + bl 0x37e5b6cc + bl 0x37e5bda4 (reloc/open_into), depois bl 0x37e5c324  PROVEN disasm
 -> 0x37e5c324 (image_setup_libfdt shape): bl fdt_chosen @ 0x37e5c344, depois bl arch_fixup_fdt @ 0x37e5c35c (0x37e211f8), bl board setup @ 0x37e5c37c (0x37e29ac8), pack/fixups  PROVEN disasm + error strings
 -> 0x37e21284 (ARM64 entry): ldr x0,[x19+0xe8] (entry), ldr x2,[x19+0x100] (FDT), x1=0xf81, b 0x37e19264  PROVEN disasm
 -> 0x37e19264: x20=x0, x21=x1, x22=x2; x0=0; x1=x21; x2=x22; eret EL2->EL1  PROVEN disasm
```

`[images+0x108]` nao e "campo do FDT", e `ft_len` (ver Fase 2). O gate em
`0x37e21248` e `if (ft_len==0) hang`, nao `if (fdt==0) skip`. Boot com
sucesso implica `ft_len!=0` e `0x37e5b800==0` por logica de hang,
mas o valor runtime de `ft_len` no path `bootm 0x1080000` e `UNKNOWN`
(sem leitura runtime).

Detalhe das duas chamadas a `0x37e255c8` em `bootm`: `0x37e24cc0` com
`w4=0,w6=0` (early, tbz w22,#0/#1 pulam env/decrypt) e `0x37e24ff0` com
`w4=0x70f,w6=1` (full). `0x70f` = START+FINDOS+FINDOTHER+LOADOS +
PREP+FAKE_GO+GO por `include/bootm.h` (reference, `INFERRED` para o binario).
O FDT so e tocado no segundo caminho via OS dispatch.

## `fdt_chosen`

Entry `0x37e297b8`, `OFFLINE_ONLY` (trace em `fdt_chosen_37e297b8.txt`):

```text
mov x20,x0 (fdt) -> bl fdt_check_header (0x37ea14e0)
 -> tbz w0,#31 fail -> "fdt_chosen: %s"
 -> fdt_find_or_add_subnode(fdt,0,"chosen") (0x37e2956c, "chosen" @ 0x37ec09d1)
 -> env_get("bootargs") @ 0x37e29814 (0x37ebf453)
 -> null -> return 0 (sem escrita, sem erro)
 -> strlen + fdt_setprop(fdt,node,"bootargs",s,len+1) @ 0x37e29840 (0x37ea28c4)
 -> tbz w0,#31 success -> return 0; fail -> "WARNING: could not set bootargs %s." + return errno
```

Caller relevante para boot normal: `0x37e5c344` dentro de `0x37e5c324`.
`PROVEN` por `callers(0x37e297b8) = {0x37e5c344, 0x37e293e4}` + shape de
`0x37e5c324` + error strings `ERROR: /chosen node create failed` /
`ERROR: arch-specific fdt fixup failed`. Registro: `x0=x1=[images+0x100]`
(mov x0,x1 @ 0x37e5c334; mov x19,x1 @ 0x37e5c340; x1 veio de
`ldr x1,[x19+0x100]` em `0x37e5b864`). Logo o `fdt` e o campo `ft_addr`.

Outro caller `0x37e293e4` e handler do comando `fdt` (cmd_tbl idx 49,
func `0x37e2852c`), com `ldr x0,[x21]` (blob do comando) + `bl fdt_chosen`.
Nao esta no path `bootm`; e capacidade mapeada, nao demonstrada. `PROVEN`
que nao e o path normal (disasm mostra parse de subcomando `fdt chosen`).

Return/branch (`fdt_setprop`):

```text
fdt_setprop == 0 -> w19=0, tbz bit31==0 -> return 0 -> caller 0x37e5c348 tbz bit31==0 -> arch_fixup  PROVEN estatico
fdt_setprop != 0 (negativo, bit31==1) -> WARNING + return errno -> caller imprime ERROR /chosen + w20=-1 -> return -1 -> 0x37e5b800 propaga (sem overwrite de w0) -> 0x37e21258 !=0 -> printf + hang  INFERRED (propagacao provada por disasm, hang provado por strings/calls)
env_get null -> return 0 sem escrita, sem WARNING; caller segue como sucesso  PROVEN
```

Nao ha indicacao estatica de falha no path stock: strings de erro existem
mas inacessiveis sem runtime. Boot com sucesso e evidencia INFERRED (nao
PROVEN) de `return==0`, porque o path de erro pendura em vez de bootar
stock.

## Post-fdt_chosen mutations

Depois de `fdt_chosen`, o mesmo ponteiro `x19` (=`[images+0x100]`) segue em
`0x37e5c324` sem copia:

```text
fdt_chosen (x19) -> arch_fixup_fdt(x19) @ 0x37e5c35c (0x37e211f8: ldr [x18] + bl 0x37e298c0, fixup de memoria/reserva)  OFFLINE_ONLY
 -> board/system setup(x19) @ 0x37e5c37c (0x37e29ac8: /aliases + ethaddr/ethernet%d, sem bootargs)  OFFLINE_ONLY
 -> ldr w2,[x19+4]; rev; bl 0x37ea3c38 + bl 0x37e29c70 (pack/totalsize) + bl 0x37ea3d28 + bl 0x37e295e8 (mem reserve/move) + bl 0x37e5c31c  OFFLINE_ONLY, todos in-place no mesmo blob
```

Busca ampla por `bootargs`/`reboot_mode`/`androidboot.selinux`/`/chosen`
no binario: 9/9 consumidores do round54 confirmados de novo via
`refs(0x37ebf453)` (6 adrp+add + 2 bl ja cobertos + gate). Nenhum outro
`fdt_setprop(/chosen,bootargs)` alem de `fdt_chosen` e `do_bootvx_fdt`
(`0x37e2646c`, path bootvx, mesmo conteudo env). `rpmb_state` fixup
(`0x37e57b5c`) e dispatch-only sem callers, fora do path. `bootm_load_os`
(`0x37e5b880`) e `bootm` fazem `setenv bootargs` append-only
(header `dtbo_idx/otg/buildvariant` + `verifiedbootstate` orange/green +
`defendkey` recovery-only + bookkeeping `0x%x`), nenhum reescreve
`selinux`/`reboot_mode`. `STATUS: nenhuma rotina posterior que substitua
/chosen encontrada (OFFLINE_ONLY negativo, escopo: string+census, nao
prova global)`.

Copia anterior a `fdt_chosen` existe: `0x37e5bda4` (reloc/open_into)
atualiza `[images+0x100]` e `[images+0x108]` (str x19,[x25] / str x21,[x24]
no tail). Logo o blob modificado por `fdt_chosen` e o blob pos-reloc, nao
necessariamente os bytes crus de `0x01000000`. `INFERRED` que ha reloc;
`UNKNOWN` se `x2` final e `0x01000000` in-place ou copia relocada (sem
leitura runtime nao da para fechar byte-equality).

`memcpy/memmove/decrypt/uncompress` posteriores sobre o FDT nao
encontrados no path Linux apos `0x37e5c324`. Decrypt-skip em
`0x37e25d0c` (tbz w22,#2) e anterior ao FDT fixup no fluxo
`bootm_load_os`, nao posterior. `STATUS: UNKNOWN para conteudo runtime,
PROVEN para ausencia de segundo escritor /chosen no estatico`.

## Reboot mode provenance

`storeargs = get_rebootmode;setenv bootargs ${initargs} ... androidboot.reboot_mode=${reboot_mode} ...` (`0x37eb6adb`, `PROVEN` por dump).
`get_rebootmode @ 0x37e60478` (cmd_tbl, `PROVEN`): le `0xc810023c`
bits `[15:12]` + jump table para `setenv reboot_mode <val>` + `run`
`storeargs`-relacionado; fallback le env `reboot_mode`. `reboot_mode`
defensivo em `bootm @ 0x37e24eb4` (adrp 0x37ec016f) so e lido no gate
`defendkey` recovery-only, nao reescrito no path fastboot. Default
`reboot_mode_android=normal @ 0x37eb6947` (`PROVEN`), mas o campo que
divergiu no round53 foi `androidboot.reboot_mode` (de `${reboot_mode}`),
nao `reboot_mode_android`.

Busca por quem forca `normal` no FDT: zero hits alem de defenv e
`switch_bootmode` script (que seta `reboot_mode_android normal` antes de
`run storeargs` em varios branches, mas `switch_bootmode` nao roda entre
verify e `bootm` no round53, sem reboot). Nenhum literal C emite
`reboot_mode=normal` para `/chosen`. `STATUS: origem BL33 de
reboot_mode=normal no FDT nao encontrada (OFFLINE_ONLY negativo)`.
O valor `normal` observado no Android nao tem emissor BL33; ou veio de
outro blob/FDT, ou de default do init quando a prop esta ausente/divergente
(`UNKNOWN`, lado Linux, ver Round53).

`reboot_mode` e util como discriminador: como `selinux` e `reboot_mode`
divergiram juntos enquanto o resto ficou igual, nao foi "somente selinux
tratado especialmente". Foi par inteiro, consistente com FDT
perdido/substituido ou string inteira trocada, nao com filtro de um campo.

## Kernel Image

Stock `boot_unpack/kernel` (9.8 MiB) e container `AMLSECU!` cifrado
(`PROVEN` por header `ver 0x0905 nblk 3`, sem `Linux version`, sem gzip).
`grep` direto por `androidboot.selinux`/`reboot_mode=normal`/`bootargs`/
`/chosen` retorna 0 hits, mas isso nao prova nada sobre o kernel real:
bytes cifrados. `STATUS: UNKNOWN por cifra (nao repetir grep como prova)`.

Rebuilt `build-aq/arch/arm64/boot/Image` (27 MiB, aproximacao McMCCRU, nao
stock) tem 9 `chosen` / 5 `bootargs` (OF core), 0 `androidboot.selinux`
(esperado: `androidboot.*` e parse do init, nao do kernel). Citado so como
referencia, nao como evidencia do stock.

Ground truth que fecha: `/proc/config.gz` do kernel em execucao (5691
linhas, salva no round54): `CONFIG_CMDLINE=""`, sem FORCE/EXTEND.
Logo o kernel usa cmdline do bootloader verbatim. `STATUS: PROVEN
(artefato) para ausencia de override compilado`. `CONFIG_CMDLINE` do
`aquaman-config` concorda (aproximacao). Nenhuma rotina kernel que fabrique
`enforcing`/`normal` foi auditada aqui (fora de escopo desta rodada;
init nao auditado).

## DTB provenance

Tres blobs distintos, nao tratar como iguais:

1. `dt.img` (firmware, 59424 B, cifrado, `PROVEN` por magic ausente).
2. `artifacts/aquaman.dtb` (RAM `0x01000000`, 58280 B, magic `d00dfeed`,
   totalsize==filelen, `dtc` zero erros no round54, `PROVEN` valido).
   Busca: 0 `chosen`, 0 `bootargs`, 0 `selinux`, 0 `reboot_mode`
   (`PROVEN` por contagem, artefato `dtb_provenance.txt`). Consistente com
   U-Boot criando `/chosen` em `bootm` (fdt_chosen/add_subnode).
3. `boot.img` second (61440 B @ `second_addr 0xf00000`, cifrado, nao-FDT,
   `PROVEN` por dump; e `dtbo`/second cifrado, nao o FDT de boot).
   `boot.img` header cmdline = `androidboot.dtbo_idx=0 otg_device=1
   buildvariant=user` (explica o extra do kernel, `PROVEN`).

`dtb_mem_addr=0x1000000` (htab/arena concordam no round54, `HARDWARE_OBSERVED`
anterior). Blob dump tem espaco livre (round54: 6404 B tail; aqui
totalsize==58280, sem `/chosen`, espaco para `bootargs` ~832 B).
`STATUS: falta de espaco REFUTED`. `STATUS: DTB baked bootargs REFUTED
para o dump (sem /chosen)`. `STATUS: segundo DTB entregue ao Linux
UNKNOWN` (o second cifrado nao e FDT legivel; se ha overlay dtbo aplicado
via `0x37e5bac8`-style ou `store dtbo`, nao foi rastreado nesta rodada e
nao toca `/chosen/bootargs` no estatico visto).

`DTB recovered from RAM != DTB actually passed to Linux` ate prova em
contrario se `0x37e5bda4` relocar (INFERRED). Nao assumir igualdade de bytes.

## EL2 -> EL1

`0x37e21284` ARM64 path (`PROVEN` disasm em `kernel_entry_37e21284.txt`):

```text
ldrb w0,[x19+0xe3]; cmp #2; b.ne fallback blr x21
ldr x0,[x19+0xe8] (entry = [images+0xe8])
ldr x2,[x19+0x100] (FDT = [images+0x100] = ft_addr)
x1 = 0xf81; b 0x37e19264
```

`0x37e19264` (`PROVEN` disasm em `eret_37e19264.txt`):

```text
mov x20,x0; mov x21,x1; mov x22,x2
sctlr_el2 clear; sctlr_el1 set; hcr=0; isb
spsr=0x1d3; elr=x20; x0=0; x1=x21; x2=x22; eret
```

Logo `x2_EL1 == [images+0x100]` pos-fixup, sem SMC no handoff (`PROVEN`
estatico; SMC e so verify-time em `0x37e24cf0/0x37e24f90`). Nenhum outro
`eret` no path Linux. `STATUS: x2 == mesmo campo modificado por
fdt_chosen (PROVEN estrutural)`. `STATUS: igualdade de bytes UNKNOWN`
(depende de reloc runtime + return runtime).

OS table `0x37eb5658 -> 0x37e21378 -> 0x37e2122c -> 0x37e5b800 ->
0x37e5c324 -> fdt_chosen` e o grafo textual pedido (`PROVEN` arestas por
`bl`, `INFERRED` a aresta via ponteiro OS table por falta de `bl`
direto, mas slot dump prova o ponteiro).

## Round53 explanation

Fato: htab autoritativo 832 B `df6c9576` (`permissiv`+`fastboot`) entregue a
`imgread success` + `bootm`, Android stock com `enforcing`+`normal`.
Resto igual + extras explicados (`dtbo_idx` header, `verifiedbootstate`
orange bootm-append, `avb_version/vbmeta.*` AVB, `bootreason` BCB/init
plausivel sem string BL33, `fake_battery` origem aberta).

Explicacoes vagas rejeitadas sem ponto de transformacao:

* "Android mudou" / "kernel sanitizou": sem rotina localizada. `REFUTED`
  como explicacao BL33; `UNKNOWN` como comportamento init (nao auditado).
* "U-Boot ignorou": `REFUTED` no estatico (fdt_chosen existe, e chamado no
  path, todos escritores usam env).
* "bootargs sobrescrito por outro builder": `REFUTED` no estatico (apenas
  appends pequenos conhecidos; nenhum emissor de `enforcing`/`normal`).

Classificacao: `UNKNOWN` (fronteira estreitada). Evidencia principal: par
duplo independente diverge junto, sem emissor BL33, com hang logico se
fixup falhasse. Candidatos restantes ordenados, nao testados: (a) FDT
trocado/relocado apos `fdt_chosen` (`x2 != blob modificado`, `UNKNOWN`);
(b) env lido em `fdt_chosen` ja divergente do verificado (rebuilder entre
verify e fixup, `UNKNOWN` mas sem candidato estatico); (c) init/Linux
derivando `ro.boot.*` sem `/chosen/bootargs` verbatim (`UNKNOWN`,
requer teste discriminador, nao novo grep).

## Root relevance

Cadeia em questao e so:

```text
BL33 arbitrary write -> input -> FDT efetivo -> Linux
```

Nada aqui avanca para root. `bootargs -> Linux` continua `REFUTED` nesta
forma (round53) com um link `UNKNOWN` (fixup runtime vs FDT final vs init).
Nenhum `uid=0`, nenhum bypass SMC, nenhum init payload auditado. Nao
promover nada a `HARDWARE_REPRODUCED` nesta rodada (sem hardware).

## Next hardware experiment

Apenas um, e so se a previsao abaixo for aceita. Teste de identidade do
FDT, nao de SELinux (Caso B):

Trocar um campo inerte que hoje concorda (ex. `androidboot.wificountrycode`
`US`->`ZZ` ou `boardid`) via `setenv`+`run storeargs` (nunca arena poke),
com `bootargs` verificado por fresh-ptr htab + oracle, depois o par E4
`imgread kernel boot 0x1080000` (checar `success` antes) + `bootm 0x1080000`,
oraculo `getprop ro.boot.wificountrycode` (+ `ro.boot.selinux` como
controle). Previsao: se o campo inerte tambem reverter, e FDT
perdido/substituido (Caso B provado, parar de testar selinux); se o inerte
passar e selinux/reboot_mode nao, e rewrite seletivo posterior (Caso D/E).
Custo: um reboot RAM-only, sem flash/saveenv/update/recovery. Nao executar
nesta rodada.

## Artifacts

* `reports/round55-fdt-identity-chain.md` (este)
* `reports/round55-fdt-identity-chain/`:
  `bootm_37e24c00.txt`, `do_bootm_linux_gate_37e2122c.txt`,
  `kernel_entry_37e21284.txt`, `eret_37e19264.txt`,
  `fixup_stage_37e5b800.txt`, `image_setup_37e5c324.txt`,
  `fdt_chosen_37e297b8.txt`, `bootvx_fdt_37e2646c.txt`,
  `os_dispatch_37e21378.txt`, `xrefs_bootargs.txt`,
  `strings_reboot_mode.txt`, `strings_chosen.txt`,
  `dtb_provenance.txt`, `bootimg_header.txt`,
  `kernel_config_cmdline.txt`
* Reuso: `reports/round54-offline-fdt-path/running_config.gz`,
  `artifacts/aquaman.dtb`, `boot.img` header.

## Validation

* `python3 tools/run_tests.py` -> `126 tests, OK` (rodar antes de fechar).
* `git diff --check` limpo.
