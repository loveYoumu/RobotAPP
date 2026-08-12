BENCHMARK_ROOT=$(SIMULATOR_ROOT)/artifact/slam

CC=g++
CFLAGS=-O2 -Wall -Wextra -std=c++11 -I$(SIMULATOR_ROOT)/interchiplet/includes
INTERCHIPLET_C_LIB=$(SIMULATOR_ROOT)/interchiplet/lib/libinterchiplet_c.a
NVCC=nvcc
CUFLAGS=--compiler-options -Wall -I$(SIMULATOR_ROOT)/interchiplet/includes

all: dirs bin/slam_cpu bin/slam_gpu bin/slam_npu

dirs:
	mkdir -p bin obj cuobj

obj/%.o: %.cpp
	$(CC) $(CFLAGS) -c $< -o $@

cuobj/%.o: %.cu
	$(NVCC) $(CUFLAGS) -c $< -o $@

bin/slam_cpu: obj/slam_cpu.o
	$(CC) $< $(INTERCHIPLET_C_LIB) -o $@

bin/slam_npu: obj/slam_npu.o
	$(CC) $< $(INTERCHIPLET_C_LIB) -o $@

bin/slam_gpu: cuobj/slam_gpu.o
	$(NVCC) -L$(SIMULATOR_ROOT)/gpgpu-sim/lib/$(GPGPUSIM_CONFIG) --cudart shared $< -o $@

clean:
	rm -f bench.txt delayInfo.txt buffer* message_record.txt pacCountInfo.txt
	rm -rf proc_r*_p*_t*

clean_all: clean
	rm -rf obj cuobj bin
