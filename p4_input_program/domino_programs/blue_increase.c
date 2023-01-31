struct Packet {
int now;
int now_plus_free;
};
int last_update;
int p_mark;
void func(struct Packet pkt) {
{ pkt.now_plus_free = pkt.now - 10;
  if (pkt.now_plus_free > last_update) {
    { p_mark = p_mark + 1;
      last_update = pkt.now; } } }}