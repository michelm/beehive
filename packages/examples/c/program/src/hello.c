
#include <stdio.h>
#include <stdlib.h>
#include <hello.h>

int main(int argc, char* argv[])
{
	return say_hello();
}

int say_hello()
{
	printf("Hello!\n");
	return EXIT_SUCCESS;
}
