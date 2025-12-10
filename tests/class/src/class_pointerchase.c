#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#ifndef NODES
#define NODES (1 << 20)
#endif
#ifndef CHASE_ROUNDS
#define CHASE_ROUNDS 16
#endif

static void shuffle(uint32_t *arr, size_t n) {
    for (size_t i = n - 1; i > 0; --i) {
        size_t j = (size_t)(rand() % (i + 1));
        uint32_t tmp = arr[i];
        arr[i] = arr[j];
        arr[j] = tmp;
    }
}

int main(void) {
    srand(1);
    uint32_t *next = (uint32_t *)aligned_alloc(64, sizeof(uint32_t) * NODES);
    if (!next) {
        perror("alloc pointerchase");
        return 1;
    }

    for (uint32_t i = 0; i < NODES; ++i) {
        next[i] = i;
    }
    shuffle(next, NODES);
    for (uint32_t i = 0; i + 1 < NODES; ++i) {
        next[next[i]] = next[i + 1];
    }
    next[next[NODES - 1]] = next[0];

    uint64_t steps = (uint64_t)NODES * CHASE_ROUNDS;
    uint32_t idx = 0;
    uint64_t sum = 0;
    for (uint64_t s = 0; s < steps; ++s) {
        idx = next[idx];
        sum += idx;
    }

    printf("class_pointerchase: nodes=%d rounds=%d steps=%llu sum=%llu idx=%u\n",
           NODES, CHASE_ROUNDS, (unsigned long long)steps,
           (unsigned long long)sum, idx);

    free(next);
    return 0;
}
