CC ?= gcc
CFLAGS ?= -O2 -static

BIN_DIR := ../bin/x86
PROGS := class_hello class_memsum class_cachethrash class_branchstorm class_matrixmul class_streamcopy class_fpvector class_matrixmul_smallsize class_pointerchase class_stream_bw class_pointerchase_rand class_bank_conflict class_stream_saturate

all: $(PROGS:%=$(BIN_DIR)/%)

$(BIN_DIR)/%: %.c | $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $<

$(BIN_DIR)/class_stream_saturate: class_stream_saturate.c | $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $<

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

clean:
	rm -f $(BIN_DIR)/$(PROGS)
