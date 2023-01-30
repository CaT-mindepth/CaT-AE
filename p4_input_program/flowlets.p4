#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) last_time;
register<bit<32>>(1) saved_hop;

const bit<32> THRESHOLD = 5;

struct headers {
}

struct metadata {
    bit<32>               flowlets_key;
    bit<32>               arrival;
    bit<32>               new_hop;
    bit<32>               next_hop;
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
            bit<32> saved_hop_tmp;
            saved_hop.read(saved_hop_tmp, 0);
            bit<32> last_time_tmp;
            last_time.read(last_time_tmp, 0);

            if (meta.arrival - last_time_tmp > THRESHOLD) {
                saved_hop_tmp = meta.new_hop;
            }

            last_time_tmp = meta.arrival;
            meta.next_hop = saved_hop_tmp;

            saved_hop.write(0, saved_hop_tmp);
            last_time.write(0, last_time_tmp);

        }
    }

    table flowlets {
        key = {
            meta.flowlets_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        flowlets.apply();
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
