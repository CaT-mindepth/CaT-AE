struct Packet {
int tcpseq;
};
int count;
int maxseq;
void func(struct Packet pkt) {
{ if (pkt.tcpseq < maxseq) {
    { count = count + 1; }
  } else {
    { maxseq = pkt.tcpseq; } } }}
