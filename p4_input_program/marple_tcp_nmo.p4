#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) count;
register<bit<32>>(1) maxseq;

struct headers {
}

struct metadata {
    bit<32>               marple_tcp_nmo_key;
    bit<32>               tcpseq;
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
            bit<32> maxseq_tmp;
            maxseq.read(maxseq_tmp, 0);

            if (meta.tcpseq < maxseq_tmp) {
                count_tmp = count_tmp + 1;
            } else {
                maxseq_tmp = meta.tcpseq;
            }

            count.write(0, count_tmp);
            maxseq.write(0, maxseq_tmp);
        }
    }

    table marple_tcp_nmo {
        key = {
            meta.marple_tcp_nmo_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        marple_tcp_nmo.apply();
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
