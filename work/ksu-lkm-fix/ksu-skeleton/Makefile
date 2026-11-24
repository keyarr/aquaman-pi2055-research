kernelsu-objs := ksu.o
kernelsu-objs += allowlist.o
kernelsu-objs += apk_sign.o
kernelsu-objs += sucompat.o
kernelsu-objs += throne_tracker.o
kernelsu-objs += core_hook.o
kernelsu-objs += ksud.o
kernelsu-objs += embed_ksud.o
kernelsu-objs += kernel_compat.o
kernelsu-objs += ksu_compat_syms.o
kernelsu-objs += hook_runtime.o
kernelsu-objs += hook_stubs.o

kernelsu-objs += selinux/selinux.o
kernelsu-objs += selinux/sepolicy.o
kernelsu-objs += selinux/rules.o

obj-m += kernelsu.o

KSU_VERSION := 12851

ccflags-y += -DKSU_VERSION=$(KSU_VERSION)
ccflags-y += -DEXPECTED_MANAGER_SIZE=0x3e6
ccflags-y += -DEXPECTED_MANAGER_HASH=\"79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7\"
ccflags-y += -I$(srctree)/security/selinux -I$(srctree)/security/selinux/include
ccflags-y += -I$(objtree)/security/selinux -I$(src)/include
ccflags-y += -include $(srctree)/include/uapi/asm-generic/errno.h
ifdef KSU_ALLOWLIST_IO_VIA_KSUD
ccflags-y += -DCONFIG_KSU_ALLOWLIST_IO_VIA_KSUD
endif
ifdef KSU_NO_EXT4_SYSFS_NUKE
ccflags-y += -DCONFIG_KSU_NO_EXT4_SYSFS_NUKE
endif
ccflags-y += -fno-stack-protector
ccflags-y += -Wno-implicit-function-declaration -Wno-strict-prototypes -Wno-int-conversion
ccflags-y += -Wno-declaration-after-statement -Wno-unused-function

$(info -- KernelSU-Next version: $(KSU_VERSION))
