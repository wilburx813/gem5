#include <stdio.h>
#include <unistd.h>

int main(void) {
    puts("class_hello: starting");
    for (int i = 0; i < 5; ++i) {
        printf("tick %d\n", i);
        fflush(stdout);
        usleep(100000);
    }
    puts("class_hello: done");
    return 0;
}
