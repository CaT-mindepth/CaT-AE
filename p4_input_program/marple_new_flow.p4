#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) count;

struct headers {
}

struct metadata {
    bit<32>               marple_new_flow_key;
    bit<32>               new;
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
            if (count_tmp == 0) {
                count_tmp = 1;
                meta.new = 1;  
            } 
            count.write(0, count_tmp);
        }
    }

    table marple_new_flow {
        key = {
            meta.marple_new_flow_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        marple_new_flow.apply();
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
