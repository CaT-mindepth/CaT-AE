#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) last_update;
register<bit<32>>(1) p_mark;

const bit<32> FREEZE_TIME = 10;
const bit<32> DELTA1 = 1;

struct headers {
}

struct metadata {
    bit<32>               blue_increase_key;
    bit<32>               now_plus_free;
    bit<32>               now;
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

            bit<32> last_update_tmp;
            last_update.read(last_update_tmp, 0);
            bit<32> p_mark_tmp;
            p_mark.read(p_mark_tmp, 0);
            
            meta.now_plus_free = meta.now - FREEZE_TIME;
            if (meta.now_plus_free > last_update_tmp) {
                p_mark_tmp = p_mark_tmp + DELTA1;
                last_update_tmp = meta.now;
            }

            last_update.write(last_update_tmp, 0);
            p_mark.write(p_mark_tmp, 0);
        }
    }

    table blue_increase {
        key = {
            meta.blue_increase_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        blue_increase.apply();
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
