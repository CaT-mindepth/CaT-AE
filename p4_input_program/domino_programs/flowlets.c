struct Packet {
int arrival;
int new_hop;
int next_hop;
};
int last_time;
int saved_hop;
void func(struct Packet pkt) {
{ if (pkt.arrival - last_time > 5) {
    { saved_hop = pkt.new_hop; } }
  last_time = pkt.arrival;
  pkt.next_hop = saved_hop; }}
