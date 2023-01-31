struct Packet {
int rtt;
int size_bytes;
};
int input_traffic_Bytes;
int input_traffic_Bytes;
int num_pkts_with_rtt;
int sum_rtt_Tr;
void func(struct Packet pkt) {
{ input_traffic_Bytes = input_traffic_Bytes + pkt.size_bytes;
  if (pkt.rtt < 30) {
    { sum_rtt_Tr = sum_rtt_Tr + pkt.rtt;
      num_pkts_with_rtt = num_pkts_with_rtt + 1; } } }}
