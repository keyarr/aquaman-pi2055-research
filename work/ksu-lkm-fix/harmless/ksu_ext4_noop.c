#include <linux/init.h>
#include <linux/module.h>
#include <linux/printk.h>

static int __init ksu_ext4_noop_init(void)
{
	pr_info("ksu_ext4_noop: loaded, no sysfs or ext4 changes\n");
	return 0;
}

static void __exit ksu_ext4_noop_exit(void)
{
}

module_init(ksu_ext4_noop_init);
module_exit(ksu_ext4_noop_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Harmless module used to validate module load with ext4 sysfs nuke disabled");
