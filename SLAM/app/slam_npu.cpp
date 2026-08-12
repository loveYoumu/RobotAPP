#include <cstdint>
#include <cstdlib>
#include <iostream>

#include "apis_c.h"
#include "../../interchiplet/includes/pipe_comm.h"

InterChiplet::PipeComm global_pipe_comm;

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    const int id_x = std::atoi(argv[1]);
    const int id_y = std::atoi(argv[2]);
    std::uint64_t metadata[8] = {};
    std::uint64_t ack[8] = {};
    unsigned long long time_now = 1;
    std::string file_name = InterChiplet::receiveSync(5, 5, id_x, id_y);
    global_pipe_comm.read_data(file_name.c_str(), metadata, sizeof(metadata));
    long long time_end = InterChiplet::readSync(
        time_now, 5, 5, id_x, id_y, sizeof(metadata), 0);

    // Classic ORB-SLAM3 has no neural-network operator. Keep the NPU in the
    // topology but do not fabricate tensor work or dynamic power.
    ack[0] = metadata[0];
    ack[1] = 0;
    file_name = InterChiplet::sendSync(id_x, id_y, 5, 5);
    global_pipe_comm.write_data(file_name.c_str(), ack, sizeof(ack));
    InterChiplet::writeSync(time_end, id_x, id_y, 5, 5, sizeof(ack), 0);
    std::cout << "SLAM NPU endpoint complete: idle/control-only\n";
    return 0;
}
