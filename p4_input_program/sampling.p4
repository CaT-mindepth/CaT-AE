#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) count;

const bit<32> N = 30;

struct headers {
}

struct metadata {
    bit<32>               sample_key;
    bit<32>               sample;
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
            bit<32> count_tmp;
            count.read(count_tmp, 0);
            if (count_tmp == N - 1) {
                meta.sample = 1;
                count_tmp = 0;
            } else {
                meta.sample = 0;
                count_tmp = count_tmp + 1;
            }
            count.write(0, count_tmp);
        }
    }

    table sampling {
        key = {
            meta.sample_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        sampling.apply();
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
