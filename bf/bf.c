#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CELL uint8_t
#define LDEPTH_MAX 100

struct mem {
	size_t size;
	CELL *data;
};

int debug = 0;

// cell 0 to pos_inf
struct mem mem_pos;

// cell -1 to neg_inf
struct mem mem_neg;

// current memory address
int vp;
// program counter
int pc;

// expands a mem and its size
void expand_memory(struct mem *mem) {
	mem->size++;
	if (debug)
		fprintf(stderr, "Expanding memory at %p to %d elements\n", mem, mem->size);

	mem->data = realloc(mem->data, mem->size);
	mem->data[mem->size-1] = 0;
}

// takes a virtual address and returns a pointer to its value (allocates memory if necessary)
CELL *conv_vp(int vp) {
	if (vp < 0) {
		// -1 -> 0
		vp = -vp - 1;
		if (vp >= mem_neg.size) {
			expand_memory(&mem_neg);
		}

		return &mem_neg.data[vp];
	} else {
		if (vp >= mem_pos.size) {
			expand_memory(&mem_pos);
		}

		return &mem_pos.data[vp];
	}
}

void main(int argc, char *argv[]) {
	char *program;
	long prog_length;

	for(int i = 0; i < argc-1; i++){
		if(strcmp("-d",argv[i]) == 0){
			debug++;
		}
	}

	FILE *infile = fopen(argv[argc-1], "r");
	if (infile) {
		fseek(infile, 0, SEEK_END);
		prog_length = ftell(infile);
		fseek(infile, 0, SEEK_SET);
		program = malloc(prog_length);

		if (program) {
			fread(program, 1, prog_length, infile);
		}

		fclose(infile);
	} else {
		fprintf(stderr, "Couldn't open file %s\n", argv[1]);
		fprintf(stderr, "Usage: %s [-d] bf_program\n", argv[0]);
		exit(EXIT_FAILURE);
	}


	if (program) {
		if (debug)
			fprintf(stderr, "Read program (length: %d)\n", prog_length);
	} else {
		fputs("Reading the program failed\n", stderr);
		exit(EXIT_FAILURE);
	}

	vp = 0;
	CELL *c = conv_vp(vp);
	char inchar;
	// used to find the end of a loop when skipping over the code inside
	int seek_loop_end = 0;
	int lstack[LDEPTH_MAX];
	int ldepth = 0;

	while (pc < prog_length) {
		char ins = program[pc];

		pc++;

		if (seek_loop_end) {
			if (ins == '[') {
				seek_loop_end++;
			} else if (ins == ']') {
				seek_loop_end--;
			}

			continue;
		}

		if (debug)
			fprintf(stderr, "Executing instruction at pc=%d: %c (mem: loc %d, val %d (0x%x))\n", pc, ins, vp, *c, *c);

		switch (ins) {
			case '<':
				c = conv_vp(--vp);
				break;
			case '>':
				c = conv_vp(++vp);
				break;
			case '-':
				(*c)--;
				break;
			case '+':
				(*c)++;
				break;
			case '.':
				putchar(*c);
				fflush(stdout);
				break;
			case ',':
				inchar = getchar();
				if (inchar == EOF) {
					if (debug)
						fputs("Reached EOF, not changing cell value\n", stderr);
				} else {
					if (debug)
						fprintf(stderr, "Input character: %c (0x%1x)\n", inchar, inchar);
					*c = inchar;
				}
				break;
			case '[':
				if (*c == 0) {
					seek_loop_end = 1;
				} else {
					if (ldepth >= LDEPTH_MAX - 2) {
						fprintf(stderr, "Error: too many nested loops");
						exit(EXIT_FAILURE);
					}
					lstack[ldepth++] = pc - 1;
				}
				break;
			case ']':
				if (*c != 0) {
					// go back to the start of the loop
					pc = lstack[--ldepth];
				} else {
					// no need to go back and then seek forward, just continue on
					ldepth--;
				}
				break;
		}
	}
}
