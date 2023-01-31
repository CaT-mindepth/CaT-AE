#include <core.p4>
#include <v1model.p4>

register<bit<32>>(1) input_traffic_Bytes;
register<bit<32>>(1) sum_rtt_Tr;
register<bit<32>>(1) num_pkts_with_rtt;

const bit<32> MAX_ALLOWABLE_RTT = 30;

struct headers {
}

struct metadata {
    bit<32>               rcp_key;
    bit<32>               rtt;
    bit<32>               size_bytes;
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

            bit<32> input_traffic_Bytes_tmp;
            input_traffic_Bytes.read(input_traffic_Bytes_tmp, 0);
            bit<32> sum_rtt_Tr_tmp;
            sum_rtt_Tr.read(sum_rtt_Tr_tmp, 0);
            bit<32> num_pkts_with_rtt_tmp;
            num_pkts_with_rtt.read(num_pkts_with_rtt_tmp, 0);

            input_traffic_Bytes_tmp = input_traffic_Bytes_tmp + meta.size_bytes;
            if (meta.rtt < MAX_ALLOWABLE_RTT) {
                sum_rtt_Tr_tmp = sum_rtt_Tr_tmp + meta.rtt;
                num_pkts_with_rtt_tmp = num_pkts_with_rtt_tmp + 1;
            }

            input_traffic_Bytes.write(input_traffic_Bytes_tmp, 0);
            sum_rtt_Tr.write(sum_rtt_Tr_tmp, 0);
            num_pkts_with_rtt.write(num_pkts_with_rtt_tmp, 0);
        }
    }

    table rcp {
        key = {
            meta.rcp_key : exact;
        }
        actions = {
            set_pkt;
        }
        size = 1;
    } 

    apply {
        rcp.apply();
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
