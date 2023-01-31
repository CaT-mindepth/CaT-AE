struct Packet {
int member;
};
int first_filter;
int second_filter;
int third_filter;
void func(struct Packet pkt) {
{ if (first_filter != 0 && second_filter != 0 && third_filter != 0) {
    { pkt.member = 1; }
  } else {
    { pkt.member = 0; } }
  first_filter = 1;
  second_filter = 1;
  third_filter = 1; }}