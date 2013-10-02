
#include <stdio.h>
#include <stdlib.h>
#include <foo.h>
#include <bar.h>

int main(int argc, char* argv[])
{
	printf("%s %s\n", foo(), bar());
	return EXIT_SUCCESS;
}

