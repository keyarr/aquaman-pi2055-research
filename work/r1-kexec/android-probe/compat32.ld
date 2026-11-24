ENTRY(_start)
PHDRS
{
	text PT_LOAD FLAGS(7);		/* PF_R | PF_W | PF_X */
}
SECTIONS
{
	. = 0x8000;
	.text : {
		*(.text*)
		*(.rodata*)
		*(.data*)
		*(.bss*)
	} :text
	/DISCARD/ : { *(.comment*) *(.ARM.attributes*) }
}
