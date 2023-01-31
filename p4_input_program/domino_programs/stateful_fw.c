struct Packet {
int array_index;
int drop;
int dst;
int src;
};
int established;
void func(struct Packet pkt) {
{ pkt.array_index = pkt.src + pkt.dst;
  if (pkt.src == 20) {
    { established = 1; }
  } else {
    { if (pkt.dst == 20) {
        { if (established == 0) {
            { pkt.drop = 1; }
          } else {
            { pkt.drop = 0; } } } } } } }}
