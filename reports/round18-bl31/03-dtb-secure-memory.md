memreserve entries: none (empty map)
/psci                                  compatible           "arm,psci-0.2"
/psci                                  method               "smc"
/secmon                                compatible           "amlogic, secmon"
/secmon                                memory-region        <0xf>
/secmon                                in_base_func         <0x82000020>
/secmon                                out_base_func        <0x82000021>
/secmon                                reserve_mem_size     <0x300000>
/securitykey                           compatible           "aml, securitykey"
/securitykey                           storage_query        <0x82000060>
/securitykey                           storage_read         <0x82000061>
/securitykey                           storage_write        <0x82000062>
/securitykey                           storage_tell         <0x82000063>
/securitykey                           storage_verify       <0x82000064>
/securitykey                           storage_status       <0x82000065>
/securitykey                           storage_list         <0x82000067>
/securitykey                           storage_remove       <0x82000068>
/securitykey                           storage_in_func      <0x82000023>
/securitykey                           storage_out_func     <0x82000024>
/securitykey                           storage_block_func   <0x82000025>
/securitykey                           storage_size_func    <0x82000027>
/securitykey                           storage_set_enctype  <0x8200006a>
/securitykey                           storage_get_enctype  <0x8200006b>
/securitykey                           storage_version      <0x8200006c>
/cpu_info                              compatible           "amlogic, cpuinfo"
/cpu_info                              cpuinfo_cmd          <0x82000044>
/cpu_info                              status               "okay"
/efuse                                 compatible           "amlogic, efuse"
/efuse                                 read_cmd             <0x82000030>
/efuse                                 write_cmd            <0x82000031>
/efuse                                 get_max_cmd          <0x82000033>
/efuse                                 key                  <0x19>
/efuse                                 clocks               <0x8 0x4a>
/efuse                                 clock-names          "efuse_clk"
/efuse                                 status               "ok"
/efuse                                 phandle              <0xbd>
/aml_reboot                            compatible           "aml, reboot"
/aml_reboot                            sys_reset            <0x84000009>
/aml_reboot                            sys_poweroff         <0x84000008>
/partitions/tee                        pname                "tee"
/partitions/tee                        size                 <0x0 0x2000000>
/partitions/tee                        mask                 <0x1>
/partitions/tee                        phandle              <0x2d>
/ion_dev                               compatible           "amlogic, ion_dev"
/ion_dev                               memory-region        <0x36>
/memory@00000000                       device_type          "memory"
/memory@00000000                       linux,usable-memory  <0x0 0x100000 0x0 0x3ff00000>
/reserved-memory                       #address-cells       <0x2>
/reserved-memory                       #size-cells          <0x2>
/reserved-memory                       ranges               (present)
/reserved-memory/ramoops@0x07400000    compatible           "ramoops"
/reserved-memory/ramoops@0x07400000    reg                  <0x0 0x7400000 0x0 0x200000>
/reserved-memory/ramoops@0x07400000    record-size          <0x8000>
/reserved-memory/ramoops@0x07400000    console-size         <0x8000>
/reserved-memory/ramoops@0x07400000    ftrace-size          <0x20000>
/reserved-memory/linux,secmon          compatible           "shared-dma-pool"
/reserved-memory/linux,secmon          reusable             (present)
/reserved-memory/linux,secmon          size                 <0x0 0x400000>
/reserved-memory/linux,secmon          alignment            <0x0 0x400000>
/reserved-memory/linux,secmon          alloc-ranges         <0x0 0x5000000 0x0 0x400000>
/reserved-memory/linux,secmon          phandle              <0xf>
/reserved-memory/linux,secos           status               "disable"
/reserved-memory/linux,secos           compatible           "amlogic, aml_secos_memory"
/reserved-memory/linux,secos           reg                  <0x0 0x5300000 0x0 0x2000000>
/reserved-memory/linux,secos           no-map               (present)
/reserved-memory/linux,secos           phandle              <0xc3>
/reserved-memory/linux,meson-fb        compatible           "shared-dma-pool"
/reserved-memory/linux,meson-fb        reusable             (present)
/reserved-memory/linux,meson-fb        size                 <0x0 0x800000>
/reserved-memory/linux,meson-fb        alignment            <0x0 0x400000>
/reserved-memory/linux,meson-fb        alloc-ranges         <0x0 0x3f800000 0x0 0x800000>
/reserved-memory/linux,meson-fb        phandle              <0x59>
/reserved-memory/linux,di_cma          compatible           "shared-dma-pool"
/reserved-memory/linux,di_cma          reusable             (present)
/reserved-memory/linux,di_cma          size                 <0x0 0x2000000>
/reserved-memory/linux,di_cma          alignment            <0x0 0x400000>
/reserved-memory/linux,di_cma          phandle              <0x6e>
/reserved-memory/linux,ion-dev         compatible           "shared-dma-pool"
/reserved-memory/linux,ion-dev         reusable             (present)
/reserved-memory/linux,ion-dev         size                 <0x0 0x4c00000>
/reserved-memory/linux,ion-dev         alignment            <0x0 0x400000>
/reserved-memory/linux,ion-dev         phandle              <0x36>
/reserved-memory/linux,vdin1_cma       compatible           "shared-dma-pool"
/reserved-memory/linux,vdin1_cma       reusable             (present)
/reserved-memory/linux,vdin1_cma       size                 <0x0 0x1000000>
/reserved-memory/linux,vdin1_cma       alignment            <0x0 0x400000>
/reserved-memory/linux,vdin1_cma       phandle              <0x6f>
/reserved-memory/linux,ppmgr           compatible           "shared-dma-pool"
/reserved-memory/linux,ppmgr           size                 <0x0 0x0>
/reserved-memory/linux,ppmgr           phandle              <0x6d>
/reserved-memory/linux,codec_mm_cma    compatible           "shared-dma-pool"
/reserved-memory/linux,codec_mm_cma    reusable             (present)
/reserved-memory/linux,codec_mm_cma    size                 <0x0 0xd000000>
/reserved-memory/linux,codec_mm_cma    alignment            <0x0 0x400000>
/reserved-memory/linux,codec_mm_cma    linux,contiguous-region (present)
/reserved-memory/linux,codec_mm_cma    phandle              <0x57>
/reserved-memory/linux,picdec          compatible           "shared-dma-pool"
/reserved-memory/linux,picdec          reusable             (present)
/reserved-memory/linux,picdec          size                 <0x0 0x0>
/reserved-memory/linux,picdec          alignment            <0x0 0x0>
/reserved-memory/linux,picdec          linux,contiguous-region (present)
/reserved-memory/linux,picdec          phandle              <0x6c>
/reserved-memory/linux,codec_mm_reserved compatible           "amlogic, codec-mm-reserved"
/reserved-memory/linux,codec_mm_reserved size                 <0x0 0x0>
/reserved-memory/linux,codec_mm_reserved alignment            <0x0 0x100000>
/reserved-memory/linux,codec_mm_reserved phandle              <0x58>

derived ranges (no interpretation beyond the values):
  linux,usable-memory = <0x100000 0x3ff00000> -> [0x100000,0x40000000)
  linux,secmon alloc-ranges <0x5000000 0x400000> -> [0x5000000,0x5400000)
  linux,secos reg <0x5300000 0x2000000> status=disable -> [0x5300000,0x7300000)
  /secmon reserve_mem_size <0x300000> (3 MiB) vs secmon size <0x400000> (4 MiB): mismatch noted, not resolved
  partitions/tee size <0x2000000> (32 MiB eMMC, secure OS, not BL31)
  DTB carries no BL31 code address/entry/magic; only reserved ranges + SMC ids.

