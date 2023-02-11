def to_bit_string(cons_1, cons_2, cons_3, sel_1, sel_2, sel_3, sel_4, sel_5, sel_6, rel_opcode, origin_or_updated):
    out_str = str('{0:06b}'.format(cons_1)) + str('{0:06b}'.format(cons_2)) + str('{0:06b}'.format(cons_3)) + two_mux_dic[sel_1] + three_mux_dic[sel_2] + two_mux_dic[sel_3] + three_mux_dic[sel_4] + two_mux_dic[sel_5] + three_mux_dic[sel_6] + rel_dic[rel_opcode] + origin_or_updated_dic[origin_or_updated] + '000000'
    return out_str

'''
        if (rel_op(mux_two(state, 0, sel_1), mux_three(pkt_1, pkt_2, cons_1, sel_2), rel_opcode))
        begin
                stateful_func = mux_two(state, 0, sel_3) + mux_three(pkt_1, pkt_2, cons_2, sel_4);
        end
        else
        begin
                stateful_func = mux_two(state, 0, sel_5) + mux_three(pkt_1, pkt_2, cons_3, sel_6);
        end
'''


two_mux_dic = {'state_1': '0', '0': '1'}
three_mux_dic = {'pkt_1': '00', 'pkt_2': '01', 'cons': '10'}
rel_dic = {'!=': '00', '<': '01', '>': '10', '==': '11'}
origin_or_updated_dic = {'origin': '000', 'update': '001'}

cons_1 = 0
cons_2 = 1
cons_3 = 0
sel_1 = '0'
sel_3 = '0'
sel_5 = 'state_1'
sel_2 = 'pkt_1'
sel_4 = 'cons'
sel_6 = 'cons'
rel_opcode = '!='
origin_or_updated = 'origin'

assert to_bit_string(0, 1, 0, 'state_1', 'cons', '0', 'cons', 'state_1', 'cons', '==', 'origin') == '00000000000100000001011001011000000000', "marple_new test failed"
print(to_bit_string(cons_1, cons_2, cons_3, sel_1, sel_2, sel_3, sel_4, sel_5, sel_6, rel_opcode, origin_or_updated))
