static long execve(const char *path, char *const argv[], char *const envp[])
{
	register long x0 asm("x0") = (long)path;
	register long x1 asm("x1") = (long)argv;
	register long x2 asm("x2") = (long)envp;
	register long x8 asm("x8") = 221;

	asm volatile("svc #0"
		: "+r"(x0)
		: "r"(x1), "r"(x2), "r"(x8)
		: "memory");
	return x0;
}

static void exit(int status)
{
	register long x0 asm("x0") = status;
	register long x8 asm("x8") = 93;

	asm volatile("svc #0" : : "r"(x0), "r"(x8) : "memory");
	for (;;)
		;
}

int main(int argc, char **argv, char **envp)
{
	argv[0] = "su";
	execve("/system/bin/su", argv, envp);
	return 127;
}

void _start(void)
{
	char **stack;

	asm volatile("mov %0, sp" : "=r"(stack));
	int argc = (int)(long)stack[0];
	char **argv = stack + 1;
	char **envp = argv + argc + 1;

	exit(main(argc, argv, envp));
}
