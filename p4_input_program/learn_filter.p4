#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) first_filter;
register<bit<32>>(1) second_filter;
register<bit<32>>(1) third_filter;

struct headers {
}

struct metadata {
    bit<32>               learn_filter_key;
    bit<32>               member;
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
            bit<32> first_filter_tmp;
            first_filter.read(first_filter_tmp, 0);
            bit<32> second_filter_tmp;
            second_filter.read(second_filter_tmp, 0);
            bit<32> third_filter_tmp;
            third_filter.read(third_filter_tmp, 0);

            if (first_filter_tmp != 0 && second_filter_tmp != 0 && third_filter_tmp != 0) {
                meta.member = 1;    
            } else {
                meta.member = 0;    
            }
            first_filter_tmp = 1;
            second_filter_tmp = 1;
            third_filter_tmp = 1;
            
            first_filter.write(0, first_filter_tmp);
            second_filter.write(0, second_filter_tmp);
            third_filter.write(0, third_filter_tmp);
        }
    }

    table learn_filter {
        key = {
            meta.learn_filter_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        learn_filter.apply();
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
