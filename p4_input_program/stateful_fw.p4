#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) established;

const bit<32> VALID_IP = 20;

struct headers {
}

struct metadata {
    bit<32>               stateful_fw_key;
    bit<32>               array_index;
    bit<32>               src;
    bit<32>               dst;
    bit<32>               drop;
}

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {
    state start {
        transition accept;
    }
    
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {
    }
}

control ingress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action set_pkt() {
        @atomic{
            bit<32> established_tmp;
            established.read(established_tmp, 0);

            meta.array_index = meta.src + meta.dst; // row indexed 2D array
            if (meta.src == VALID_IP) {
                established_tmp = 1;
            } else {
                if (meta.dst == VALID_IP) {
                    if (established_tmp == 0) {
                        meta.drop = 1;
                    } else {
                        meta.drop = 0;
                    }
                }
            }
            established.write(0, established_tmp);
        }
    }

    table stateful_fw {
        key = {
            meta.stateful_fw_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        stateful_fw.apply();
    }
}

control egress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {
    }
}

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
     apply {  }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply { }
}

V1Switch(
MyParser(),
MyVerifyChecksum(),
ingress(),
egress(),
MyComputeChecksum(),
MyDeparser()
) main;
