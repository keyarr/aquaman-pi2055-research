BL33 eMMC vocabulary (counts, first hits):
== mmc dev (18)
  0x37ec349c  No MMC device available
  0x37ec34b5  no mmc device at slot %x
  0x37ec3a47  - display info of the current MMC device
  0x37ec3a70  info - display info of the current MMC device
  0x37ec3aeb  mmc part - lists available partition on current mmc device
  0x37ec3b26  mmc dev [dev] [part] - show or set current mmc device [partition]
  0x37ec402b  can't find mmc device
  0x37ec454c  mmc dev %d has not been initialed
== mmc part (2)
  0x37ec3aeb  mmc part - lists available partition on current mmc device
  0x37ec584d  amlmmc part <device_num> - show partition infomation of mmc
== mmcinfo (3)
  0x37ec3a2e  mmcinfo
  0x37ec629f  mmcinfo 1
  0x37ed7dcb  [MSG]mmcinfo failed!
== amlmmc switch (3)
  0x37ec58da  amlmmc switch <device_num> <part name> - part name : boot0, boot1, user
  0x37ec609c  amlmmc switch 1 boot%d
  0x37ec60b3  amlmmc switch 1 user
== boot0 (5)
  0x37ec4ab7  boot0 success
  0x37ec4ac6  boot0 failed
  0x37ec58da  amlmmc switch <device_num> <part name> - part name : boot0, boot1, user
  0x37ed1d2b  -boot0
  0x37f60920  bootloader-boot0
== boot1 (5)
  0x37ec4ad4  boot1 success
  0x37ec4ae3  boot1 failed
  0x37ec58da  amlmmc switch <device_num> <part name> - part name : boot0, boot1, user
  0x37ed1d32  -boot1
  0x37f60940  bootloader-boot1
== gpt (37)
  0x37eb48c0  gpt_restore
  0x37eb48d0  gpt_verify_headers
  0x37eb48e8  write_mbr_and_gpt_partitions
  0x37eb4908  is_gpt_valid
  0x37eb4930  alloc_read_gpt_entries
  0x37ec4042  Writing GPT: 
  0x37ec40c7  Verify GPT: 
  0x37ec4223   Restore or verify GPT information on a device connected
== store  (35)
  0x37ebf8bc  store erase partition rsv
  0x37ebf9e6  store dtb read $dtb_mem_addr
  0x37ebfa03  %s(): [store dtb read $dtb_mem_addr] fail
  0x37ebfa3e  store dtb read %x
  0x37ec02a1  store size %s 0x%p
  0x37ec02e1  store read %s 0x%p 0 0x%llx
  0x37ec04a9  store dtb decrypt ${dtb_mem_addr}
  0x37ec2a9d  failed to store read %s.
== store_read (2)
  0x37eb42e0  store_read_ops
  0x37ed9945  Fail in store_read_ops to read %u at offset %llx.
== store dtb (7)
  0x37ebf9e6  store dtb read $dtb_mem_addr
  0x37ebfa03  %s(): [store dtb read $dtb_mem_addr] fail
  0x37ebfa3e  store dtb read %x
  0x37ec04a9  store dtb decrypt ${dtb_mem_addr}
  0x37ec5e1c  MBR not support, try [store dtb write Addr]
  0x37ec6688  store dtb iread/read/write addr <size>
  0x37ec699e  store dtb %s 0x%p 0x%x
== partition (198)
  0x37eb46d0  get_partition_from_dts
  0x37eb4860  get_partition_info_efi
  0x37eb48e8  write_mbr_and_gpt_partitions
  0x37eb4a18  _find_partition_by_name
  0x37eb4c00  _cmp_partition
  0x37eb4d38  find_virtual_partition_by_name
  0x37eb4d98  aml_get_partition_by_name
  0x37eb4db8  aml_get_virtual_partition_by_name
== partitions (21)
  0x37eb48e8  write_mbr_and_gpt_partitions
  0x37ec0bf0  /partitions
  0x37ec0bfc  %s: not find /partitions node %s.
  0x37ec372a  switch to partitions #%d, %s
  0x37ec3da9    Power cycling is required to initialize partitions after set to complete.
  0x37ec3ef5  ** No valid partitions found **
  0x37ec3fad  Error: is the partitions string NULL-terminated?
  0x37ec4179  new partition table with %d partitions is:
== tee (4)
  0x37ed4873  tee_log_level [log_level],
  0x37ed493e  tee_log_level
  0x37ed494c  update tee log level
  0x37edf647  partition-type:tee
== rsv (42)
  0x37e4cef7  RsVP
  0x37eb4b80  get_ptbl_rsv
  0x37eb4bc8  update_ptbl_rsv
  0x37ebf829  imgread pic rsv pattern.usb.efuse $loadaddr
  0x37ebf8bc  store erase partition rsv
  0x37ec0898  rsvmem check
  0x37ec08a5  rsvmem check failed
  0x37ec1e2d  off_mem_rsvmap:
== dtb_mem_addr (7)
  0x37eb6785  dtb_mem_addr=0x1000000
  0x37eb7647  recovery_from_udisk=setenv bootargs ${bootargs} aml_dt=${aml_dt} recovery_part={recovery_part} recovery_offset
  0x37eb77ae  recovery_from_flash=get_valid_slot;echo active_slot: ${active_slot};if test ${active_slot} = normal; then sete
  0x37ebf9e6  store dtb read $dtb_mem_addr
  0x37ebfa03  %s(): [store dtb read $dtb_mem_addr] fail
  0x37ec04a9  store dtb decrypt ${dtb_mem_addr}
  0x37ed6f7d  env dtb_mem_addr not defined, pls set ir or asign dtbLoadaddr
== loadaddr (18)
  0x37eb66b0  loadaddr=1080000
  0x37eb71f2  storeboot=get_system_as_root_mode;echo system_mode: ${system_mode};if test ${system_mode} = 1; then setenv fs_
  0x37eb7647  recovery_from_udisk=setenv bootargs ${bootargs} aml_dt=${aml_dt} recovery_part={recovery_part} recovery_offset
  0x37eb77ae  recovery_from_flash=get_valid_slot;echo active_slot: ${active_slot};if test ${active_slot} = normal; then sete
  0x37eb7aa9  init_display=get_rebootmode;echo reboot_mode:::: ${reboot_mode};if test ${reboot_mode} = quiescent; then seten
  0x37ebf829  imgread pic rsv pattern.usb.efuse $loadaddr
  0x37ec0ce6  .callbacks:callbacks,.flags:flags,baudrate:baudrate,bootfile:bootfile,loadaddr:loadaddr,silent:silent,stdin:co
  0x37ec6a5b  loadaddr_misc
== bootloader-boot0 (1)
  0x37f60920  bootloader-boot0
== bootloader-boot1 (1)
  0x37f60940  bootloader-boot1

at-rest layout (static, no dump performed):
  boot0/boot1 eMMC hw partitions <- bootloader.img (1.3 MiB, encrypted FIP: BL2+BL30+BL31+BL33).
  user area GPT <- DTB /partitions node (17 entries; tee 0x2000000, boot 0x1000000, recovery 0x1800000...).
  BL33 reaches eMMC via store/mmc/amlmmc/gpt cmds; mmc read is the demonstrated eMMC->RAM path.
  candidate eMMC ranges: (1) boot0/boot1 whole (FIP/BL31 at rest, encrypted);
  (2) tee partition (secure OS, not BL31); (3) dt/logo/misc (no BL31 evidence).
  no indiscriminate dump: at-rest BL31 is encrypted, only a live BL31 mapping answers E3.

