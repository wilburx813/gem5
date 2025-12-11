#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef CACHELINE_SIZE
#define CACHELINE_SIZE 64
#endif

static void die(const char *msg) {
    perror(msg);
    exit(EXIT_FAILURE);
}

static void usage(const char *prog) {
    fprintf(stderr,
            "Usage: %s [--size-mb M] [--iters N] [--stride BYTES]\n"
            "  --size-mb/-s   每个数组的总容量 (MiB，默认 128)\n"
            "  --iters/-i     迭代次数 (默认 12)\n"
            "  --stride/-r    访问步长 (字节，默认 64，对齐到 8 字节)\n",
            prog);
}

int main(int argc, char **argv) {
    size_t size_mb = 128;     // 每个数组的总容量
    size_t iters = 12;        // 更多迭代以拉高带宽
    size_t stride_bytes = 64; // 按 cacheline 步进

    static struct option opts[] = {
        {"size-mb", required_argument, 0, 's'},
        {"iters", required_argument, 0, 'i'},
        {"stride", required_argument, 0, 'r'},
        {0, 0, 0, 0}};

    int c;
    while ((c = getopt_long(argc, argv, "s:i:r:", opts, NULL)) != -1) {
        switch (c) {
        case 's':
            size_mb = strtoul(optarg, NULL, 0);
            break;
        case 'i':
            iters = strtoul(optarg, NULL, 0);
            break;
        case 'r':
            stride_bytes = strtoul(optarg, NULL, 0);
            break;
        default:
            usage(argv[0]);
            return 1;
        }
    }

    if (iters == 0) {
        fprintf(stderr, "iters must be > 0\n");
        return 1;
    }
    if (stride_bytes < sizeof(double)) {
        stride_bytes = sizeof(double);
    }

    size_t stride_elems = stride_bytes / sizeof(double);
    size_t bytes_total = size_mb * 1024ul * 1024ul;
    size_t elems_total = bytes_total / sizeof(double);
    if (elems_total < 1024) {
        fprintf(stderr, "size too small\n");
        return 1;
    }

    double *a = NULL, *b = NULL, *carr = NULL;
    if (posix_memalign((void **)&a, CACHELINE_SIZE, bytes_total) ||
        posix_memalign((void **)&b, CACHELINE_SIZE, bytes_total) ||
        posix_memalign((void **)&carr, CACHELINE_SIZE, bytes_total)) {
        die("posix_memalign");
    }

    for (size_t i = 0; i < elems_total; ++i) {
        a[i] = (double)(i & 0xFF);
        b[i] = 1.0;
        carr[i] = 2.0;
    }

    uint64_t acc = 0;
    for (size_t it = 0; it < iters; ++it) {
        for (size_t i = 0; i < elems_total; i += stride_elems) {
            double x = b[i];
            double y = carr[i];
            double out = (x + 1.0) + (y * 1.5);  // 混合读写，驱动带宽

            // 简单手动预取：跨两条 cache line，避免使用未实现指令
            size_t pf = i + 16;
            if (pf < elems_total) {
                asm volatile("prefetcht0 %0" : : "m"(b[pf]));
                asm volatile("prefetcht0 %0" : : "m"(carr[pf]));
            }

            a[i] = out;
            b[i] = out + 2.0;
            carr[i] = out - 1.0;
            acc += (uint64_t)(out * 1000.0);
        }
    }

    printf("stream_saturate finished: size_mb=%zu iters=%zu stride=%zuB checksum=%" PRIu64 "\n",
           size_mb, iters, stride_bytes, acc);

    free(carr);
    free(b);
    free(a);
    return 0;
}
