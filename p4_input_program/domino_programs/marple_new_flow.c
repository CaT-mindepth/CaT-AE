struct Packet {
int new;
};
int count;
void func(struct Packet pkt) {
{ if (count == 0) {
    { count = 1;
      pkt.new = 1; } } }}
