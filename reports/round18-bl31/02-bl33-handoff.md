== bl31 (7)
  0x37ed40f1  [rsvmem] bl31 reserved memory start: 0x%08x
  0x37ed411e  [rsvmem] bl31 reserved memory size:  0x%08x
  0x37ed4368  [rsvmem] bl31 reserved memory set addr error.
  0x37ed4401  [rsvmem] bl31 reserved memory set size error.
  0x37ed44b8  [rsvmem] bl31 reserved memory set alloc-ranges error.
  0x37ed4518  [rsvmem] bl31 reserved memory set reserve_mem_size error.
  0x37edd6e7  %s() %d: can't get buffer from bl31!
== secmon (11)
  0x37ed4254  fdt get value env_compatible /reserved-memory/linux,secmon compatible;
  0x37ed42d7  amlogic, aml_secmon_memory
  0x37ed42f2  fdt set /reserved-memory/linux,secmon reg <0x%x 0x%x>;
  0x37ed4329  fdt set /reserved-memory/linux,secmon reg <0x0 0x%x 0x0 0x%x>;
  0x37ed4397  fdt set /reserved-memory/linux,secmon size <0x%x>;
  0x37ed43ca  fdt set /reserved-memory/linux,secmon size <0x0 0x%x>;
  0x37ed4430  fdt set /reserved-memory/linux,secmon alloc-ranges <0x%x 0x%x>;
  0x37ed4470  fdt set /reserved-memory/linux,secmon alloc-ranges <0x0 0x%x 0x0 0x%x>;
  0x37ed44ef  fdt set /secmon reserve_mem_size <0x%x>;
  0x37ed46fa  fdt get value secmon_clear_range /secmon clear_range;
  0x37ed4730  fdt set /secmon clear_range <0x%x 0x%x>;
== rsvmem (27)
  0x37ec0898  rsvmem check
  0x37ec08a5  rsvmem check failed
  0x37ed40d6  [rsvmem] reserved memory:
  0x37ed40f1  [rsvmem] bl31 reserved memory start: 0x%08x
  0x37ed411e  [rsvmem] bl31 reserved memory size:  0x%08x
  0x37ed414b  [rsvmem] bl32 reserved memory start: 0x%08x
  0x37ed4178  [rsvmem] bl32 reserved memory size:  0x%08x
  0x37ed41a5  [rsvmem] get fdtaddr NULL!
  0x37ed41ce  [rsvmem] fdt addr error.
  0x37ed4212  [rsvmem] fdt get size #address-cells failed.
  0x37ed429b  [rsvmem] fdt get prop fail.
  0x37ed4368  [rsvmem] bl31 reserved memory set addr error.
  0x37ed4401  [rsvmem] bl31 reserved memory set size error.
  0x37ed44b8  [rsvmem] bl31 reserved memory set alloc-ranges error.
== shared-dma-pool (1)
  0x37ed42c7  shared-dma-pool
== sharemem (0)
== get_sharemem (0)
== bl32 (8)
  0x37ed414b  [rsvmem] bl32 reserved memory start: 0x%08x
  0x37ed4178  [rsvmem] bl32 reserved memory size:  0x%08x
  0x37ed4585  [rsvmem] bl32 reserved memory set status error.
  0x37ed462a  [rsvmem] bl32 reserved memory set addr error.
  0x37ed4659  [rsvmem] bl32 reserved memory set size error.
  0x37ed4688  [rsvmem] bl32 reserved memory set alloc-ranges error.
  0x37ed46bf  [rsvmem] bl32 reserved memory set reserve_mem_size error.
  0x37ed4759  [rsvmem] bl32 reserved memory set clear_range error.
== secos (3)
  0x37ed4553  fdt set /reserved-memory/linux,secos status okay;
  0x37ed45b6  fdt set /reserved-memory/linux,secos reg <0x%x 0x%x>;
  0x37ed45ec  fdt set /reserved-memory/linux,secos reg <0x0 0x%x 0x0 0x%x>;
== secure (24)
  0x37eb4650  key_unify_query_secure
  0x37eb47e8  key_manage_query_secure
  0x37ec6aff  img NOT signed but secure boot enabled
  0x37ec6b27  Img signed but secure boot NOT enabled
  0x37ec6bb5  Fail in _aml_get_secure_boot_kernel_size, rc=%d
  0x37ec6c80  [imgread]secureKernelImgSz=0x%x
  0x37ecfa08  secure_boot_set
  0x37ecfbe8  aml log : Secure boot EFUSE pattern programming fail [%d]!
  0x37ecfc24  aml log : Secure boot EFUSE pattern programming success!
  0x37ecfdb2  SecureBoot
  0x37ed488e  the min log level is 1, and the max log level is related to Secure OS version
  0x37ed496e  the min log level is 1, and the max log level is related to Secure OS version
  0x37ed7067  key[%s] can't read as it's secure
  0x37ed713a  secure
== trustzone (0)
== fdt set /reserved-memory (9)
  0x37ed42f2  fdt set /reserved-memory/linux,secmon reg <0x%x 0x%x>;
  0x37ed4329  fdt set /reserved-memory/linux,secmon reg <0x0 0x%x 0x0 0x%x>;
  0x37ed4397  fdt set /reserved-memory/linux,secmon size <0x%x>;
  0x37ed43ca  fdt set /reserved-memory/linux,secmon size <0x0 0x%x>;
  0x37ed4430  fdt set /reserved-memory/linux,secmon alloc-ranges <0x%x 0x%x>;
  0x37ed4470  fdt set /reserved-memory/linux,secmon alloc-ranges <0x0 0x%x 0x0 0x%x>;
  0x37ed4553  fdt set /reserved-memory/linux,secos status okay;
  0x37ed45b6  fdt set /reserved-memory/linux,secos reg <0x%x 0x%x>;
  0x37ed45ec  fdt set /reserved-memory/linux,secos reg <0x0 0x%x 0x0 0x%x>;
== fdt set /secmon (2)
  0x37ed44ef  fdt set /secmon reserve_mem_size <0x%x>;
  0x37ed4730  fdt set /secmon clear_range <0x%x 0x%x>;
== fdt get value (4)
  0x37ed41e8  fdt get value temp_env / \#address-cells;
  0x37ed4254  fdt get value env_compatible /reserved-memory/linux,secmon compatible;
  0x37ed46fa  fdt get value secmon_clear_range /secmon clear_range;
  0x37ee5258  fdt get value <var> <path> <prop>   - Get <property> and store in <var>
== fdtaddr (2)
  0x37ec1b26  fdtaddr
  0x37ed41a5  [rsvmem] get fdtaddr NULL!
== reserve_mem_size (3)
  0x37ed44ef  fdt set /secmon reserve_mem_size <0x%x>;
  0x37ed4518  [rsvmem] bl31 reserved memory set reserve_mem_size error.
  0x37ed46bf  [rsvmem] bl32 reserved memory set reserve_mem_size error.
== alloc-ranges (4)
  0x37ed4430  fdt set /reserved-memory/linux,secmon alloc-ranges <0x%x 0x%x>;
  0x37ed4470  fdt set /reserved-memory/linux,secmon alloc-ranges <0x0 0x%x 0x0 0x%x>;
  0x37ed44b8  [rsvmem] bl31 reserved memory set alloc-ranges error.
  0x37ed4688  [rsvmem] bl32 reserved memory set alloc-ranges error.
== memory-region (0)
== clear_range (3)
  0x37ed46fa  fdt get value secmon_clear_range /secmon clear_range;
  0x37ed4730  fdt set /secmon clear_range <0x%x 0x%x>;
  0x37ed4759  [rsvmem] bl32 reserved memory set clear_range error.

reading: BL33 holds no BL31 image parser/loader/header/entry.
handoff is HW-reg + SMC + DTB: cmd_rsvmem reads P_AO_SEC_GP_CFG3/4/5,
sharemem bases come from SMC 0x82000020/0x82000021, DTB is patched
via run_command fdt set (secmon reg/size/alloc-ranges, secmon
reserve_mem_size, secos reg/status). BL31 is resident before BL33.

