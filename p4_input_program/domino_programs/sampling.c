struct Packet {
int sample;
};
int count;
void func(struct Packet pkt) {
{ if (count == 29) {
    { pkt.sample = 1;
      count = 0; }
  } else {
    { pkt.sample = 0;
      count = count + 1; } } }}
