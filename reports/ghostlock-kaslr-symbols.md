# GhostLock KASLR + symbols + kernel stock (Fase 8 + Fase 9)

## Kernel stock como artefato — resultado

- boot.img -> boot_unpack/kernel 9.3M comeca com magico AMLSECU!
  (versao 0x905, 3 blocos, timestamp build 2022090612544443).
- Entropia ~8.0 bits/byte apos o header: cifrado, sem plaintext.
- m1b_kernel.bin no workspace tem 112B (stub, nao kernel).
- Conclusao: NENHUM vmlinux/Image analisavel offline hoje. A via
  "extrair e fazer pahole/Ghidra" esta BLOQUEADA sem a key AMLSECU,
  que nao vamos atacar (fora de escopo, secure world).

## O que isso tranca e o que resta

Tranca: (B) artefatos estaticos — sem text base, sem kallsyms, sem
relocs, sem DWARF, sem IKCONFIG do binario real.
Resta:
  A) direto: /proc/version, /proc/cmdline, getprop, uname (banais).
  C) side-channel: leak via futex hash timing (hazel ks_*) ou KASLR
     slide via leituras relativas — funciona SEM kallsyms, mas exige o
     primitive de reclaim funcionando primeiro (ovo e galinha
     resolvido pelo hazel: o leak mm vem antes do kernel R/W e usa so
     timing de futex + /proc/pid/mem do filho, tudo userspace).
  D) pos-R/W: com kernel read, ancora init_task por "swapper" comm +
     task list, depois deriva o resto. Igual ao hazel
     (validate_runtime_profile + find_current_task).

## Kallsyms bloqueado: nao eh impeditivo

Os tres ports assumem kallsyms fechado para shell:
- hazel: perfis com enderecos absolutos + validacao runtime por leitura
  (comm swapper + next/prev da task list). KASLR? No ARM32 4.9 FireOS
  sem KASLR efetivo para lowmem — enderecos estaveis por firmware.
- aresin: slide_leak_kernel_base + resolve_missing_offsets via kallsyms
  QUANDO disponivel (root/Magisk), senao fallback estatico. No aquaman
  sem root previo, fallback estatico nao existe ainda: precisa construir
  o primeiro perfil via kernel compilado compativel (dangal + config
  aproximado) ou via leak C antes de qualquer write.
- dnlid: usa VAs de evidencia offline so para documentar, nao para
  explorar.

Para aquaman ARM64 VA39 (CONFIG_ARM64_VA_BITS=39, PAGE_OFFSET
0xffffff8000000000): se KASLR ativo, text flutua em janela conhecida;
o leak precisa resolver o slide antes do fake fops apontar para
funcoes reais. Ordem pratica: (1) UAF + reclaim com payload que NAO
precisa de simbolo (fake lock/waiter apontando para pagina controlada
conhecida via leak mm, como o hazel faz com page_base do slab);
(2) kernel read da pagina -> ancora swapper -> resolve init_task;
(3) dai deriva fops/configfs/ashmem por leitura de ponteiros
  (ex.: file->f_op de um fd ashmem real lido via read da task? requer
  file table walk — custo alto mas factivel) OU por imagem de kernel
  compativel compilada localmente.

## Caminho recomendado para o primeiro perfil aquaman

1. Compilar dangal-p-oss (MiTV_OpenSource local) com aquaman-config
   aproximado, extrair vmlinux, pahole em todas as structs da Fase 3,
   anotar enderecos de funcoes como REFERENCIA (nao como alvo).
2. No aparelho: reachability (Fase 10) -> EDEADLK race stats (dnlid
   --race) -> leak mm (hazel ks_*) calibrado para slab ARM64 real.
3. Com kernel read: ancora swapper, constroi perfil runtime-validado.
4. So entao fake fops + cred patch.

Nada disso precisa de kallsyms aberto nem de quebrar AMLSECU.
