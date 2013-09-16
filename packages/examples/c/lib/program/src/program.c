
#include <stdio.h>
#include <stdlib.h>

extern char* foo();
extern char* bar();

int main(int argc, char* argv[]) {
	printf("%s %s\n", foo(), bar());
	return EXIT_SUCCESS;
}
