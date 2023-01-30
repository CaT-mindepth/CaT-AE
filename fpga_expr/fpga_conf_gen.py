import sys

import math

module_id = {'Parser' : 0,
            'Deparser': 5,
            'KeyExtractConf': 1,
            'CAMMaskConf': 1,
            'CAMConf': 2,
            'RAMConf': 2}
num_of_phv = 64
num_of_stages = 12
num_of_tables_per_stage = 8
num_of_match_field = 8
entries_per_table = 256

def int_to_bin_str(v, length):
    return str(format(v, 'b').zfill(length))

def parse_json(ILP_alloc):
    var_val_dict = {}
    for i in range(len(ILP_alloc['Vars'])):
        curr_var = ILP_alloc['Vars'][i]['VarName']
        curr_value = ILP_alloc['Vars'][i]['X']
        var_val_dict[curr_var] = curr_value
    return var_val_dict

def gen_table_stage_alloc(var_val_dict, table_match_part_dic, cost):
    used_table_dict = {}
    for i in range(cost):
        used_table_dict[i] = []    
    for i in range(cost):
        for table in table_match_part_dic:
            for size in range(table_match_part_dic[table]):
                var_name = "%s_M%s_stage%s" % (table, size, i)
                # print("var_name =" ,var_name)
                if var_name in var_val_dict:
                    assert var_val_dict[var_name] == 1
                    if table not in used_table_dict[i]:
                        used_table_dict[i].append(table)
    return used_table_dict

def get_modified_pkt(table_name, action_name, alu, pkt_alu_dic):
    l_to_find = [table_name, action_name, alu]
    # print("l_to_find =",l_to_find)
    for pkt_field in pkt_alu_dic:
        if l_to_find in pkt_alu_dic[pkt_field]:
            return pkt_field
    return -1

def valid_ram_list(ram_list):
    for mem in ram_list:
        if mem != "0000000000000000000000000000000000000000000000000000000000000000":
            return True
    return False

def text_gen(pkt_fields_def, tmp_fields_def, stateful_var_def, table_act_dic, table_size_dic, match_field_dic,
match_action_rule, tmp_alu_dic, state_var_op_dic, action_alu_dic, pkt_alu_dic, update_var_dic, update_state_dic,
 ILP_alloc):

# def main(argv):
#     # four table benchmark5
#     pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
#     tmp_fields_def = [] # all temporary variables
#     stateful_var_def = ['s0'] # all stateful variables

#     table_act_dic = {'ipv4_dest_vtep':['set_tunnel_termination_flag','set_tunnel_vni_and_termination_flag'],
#                     'ingress_l4_src_port':['set_ingress_src_port_range_id'],
#                     'ipv4_multicast_bridge':['multicast_bridge_s_g_hit'],
#                     'ipv4_multicast_route':['multicast_route_s_g_hit_0'],
#                     'sampling_table': ['sampling']}
#     table_size_dic = {'ipv4_dest_vtep':1024,
#                         'ingress_l4_src_port':512,
#                         'ipv4_multicast_bridge':1024,
#                         'ipv4_multicast_route':1024,
#                         'sampling_table':1}
#     match_field_dic = {'ipv4_dest_vtep' : ['pkt_2','pkt_3','pkt_4'],
#                         'ingress_l4_src_port': ['pkt_6'],
#                         'ipv4_multicast_bridge':['pkt_9','pkt_10','pkt_11'],
#                         'ipv4_multicast_route':['pkt_2','pkt_10','pkt_11'],
#                         'sampling_table': ['pkt_0']}
#     match_action_rule = {'ipv4_dest_vtep' : [({'pkt_2' : 5,'pkt_3':5,'pkt_4':5}, 'set_tunnel_vni_and_termination_flag')],
#                         'ingress_l4_src_port' : [({'pkt_6':5}, 'set_ingress_src_port_range_id')],
#                         'ipv4_multicast_bridge': [({'pkt_9':5, 'pkt_10':5,'pkt_11':5}, 'multicast_bridge_s_g_hit')],
#                         'ipv4_multicast_route':[({'pkt_2':5, 'pkt_10':5,'pkt_11':5},'multicast_route_s_g_hit_0')],
#                         "sampling_table": [({'pkt_0' : 5}, 'sampling')]}
#     tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
#     state_var_op_dic = {
#         's0':[['sampling_table','sampling','ALU1']],
#     }
#     action_alu_dic = {'ipv4_dest_vtep': {'set_tunnel_termination_flag':['ALU1'],
#                                         'set_tunnel_vni_and_termination_flag':['ALU1','ALU2']},
#                         'ingress_l4_src_port': {'set_ingress_src_port_range_id':['ALU1']},
#                         'ipv4_multicast_bridge':{'multicast_bridge_s_g_hit':['ALU1','ALU2']},
#                         'ipv4_multicast_route':{'multicast_route_s_g_hit_0':['ALU1','ALU2','ALU3','ALU4']}, 
#                         'sampling_table': {'sampling':['ALU1','ALU2']}
#                         }
#     pkt_alu_dic = {
#         'pkt_0':[['ipv4_dest_vtep','set_tunnel_termination_flag','ALU1'],['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU2']],
#         'pkt_1':[['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU1'],['sampling_table','sampling','ALU2']],
#         'pkt_5':[['ingress_l4_src_port','set_ingress_src_port_range_id','ALU1']],
#         'pkt_7':[['ipv4_multicast_bridge','multicast_bridge_s_g_hit','ALU1']],
#         'pkt_8':[['ipv4_multicast_bridge','multicast_bridge_s_g_hit','ALU2']],
#         'pkt_12':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU1']],
#         'pkt_13':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU2']],
#         'pkt_14':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU3']],
#         'pkt_15':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU4']]
#     }
#     update_var_dic = {
#         'ipv4_dest_vtep_set_tunnel_termination_flag_ALU1':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 1},
#         'ipv4_dest_vtep_set_tunnel_vni_and_termination_flag_ALU1':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 7},
#         'ipv4_dest_vtep_set_tunnel_vni_and_termination_flag_ALU2':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 1},
#         'ingress_l4_src_port_set_ingress_src_port_range_id_ALU1':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 7},
#         'ipv4_multicast_bridge_multicast_bridge_s_g_hit_ALU1':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 7},
#         'ipv4_multicast_bridge_multicast_bridge_s_g_hit_ALU2':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 1},
#         'ipv4_multicast_route_multicast_route_s_g_hit_0_ALU1':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 7},
#         'ipv4_multicast_route_multicast_route_s_g_hit_0_ALU2':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 1},
#         'ipv4_multicast_route_multicast_route_s_g_hit_0_ALU3':{"opcode": 0, "operand0": "pkt_0", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 1},
#         'ipv4_multicast_route_multicast_route_s_g_hit_0_ALU4':{"opcode": 2, "operand0": "pkt_16", "operand1": "pkt_0", "operand2": "pkt_0", "immediate_operand": 0},
#         'sampling_table_sampling_ALU2':{"opcode":9, "operand0": "s0", "operand1":"pkt_1", "operand2":"pkt_1", "immediate_operand": 29},
#     }
#     update_state_dic = {
#         'sampling_table_sampling_ALU1':"00001100"+"000000"+"000000"+"000000"+"01110100000000000101011001011000000000",
#     }
#     ILP_alloc = { "SolutionInfo": { "Status": 2, "Runtime": 4.5320987701416016e-02, "Work": 3.3978260090297384e-02, "ObjVal": 2, "ObjBound": 2, "ObjBoundC": 2, "MIPGap": 0, "IntVio": 0, "BoundVio": 0, "ConstrVio": 0, "IterCount": 0, "BarIterCount": 0, "NodeCount": 0, "SolCount": 4, "PoolObjBound": 2, "PoolObjVal": [ 2, 9, 10, 11]}, "Vars": [ { "VarName": "cost", "X": 2}, { "VarName": "ipv4_dest_vtep_M0", "X": 2}, { "VarName": "ipv4_dest_vtep_M0_set_tunnel_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M0_set_tunnel_vni_and_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M0_set_tunnel_vni_and_termination_flag_ALU2_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M1", "X": 2}, { "VarName": "ipv4_dest_vtep_M1_set_tunnel_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M1_set_tunnel_vni_and_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M1_set_tunnel_vni_and_termination_flag_ALU2_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M2", "X": 2}, { "VarName": "ipv4_dest_vtep_M2_set_tunnel_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M2_set_tunnel_vni_and_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M2_set_tunnel_vni_and_termination_flag_ALU2_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M3", "X": 2}, { "VarName": "ipv4_dest_vtep_M3_set_tunnel_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M3_set_tunnel_vni_and_termination_flag_ALU1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M3_set_tunnel_vni_and_termination_flag_ALU2_stage0", "X": 1}, { "VarName": "ingress_l4_src_port_M0", "X": 2}, { "VarName": "ingress_l4_src_port_M0_set_ingress_src_port_range_id_ALU1", "X": 1}, { "VarName": "ingress_l4_src_port_M0_set_ingress_src_port_range_id_ALU1_stage1", "X": 1}, { "VarName": "ingress_l4_src_port_M1", "X": 2}, { "VarName": "ingress_l4_src_port_M1_set_ingress_src_port_range_id_ALU1", "X": 1}, { "VarName": "ingress_l4_src_port_M1_set_ingress_src_port_range_id_ALU1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0", "X": 2}, { "VarName": "ipv4_multicast_bridge_M0_multicast_bridge_s_g_hit_ALU1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0_multicast_bridge_s_g_hit_ALU1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0_multicast_bridge_s_g_hit_ALU2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0_multicast_bridge_s_g_hit_ALU2_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1", "X": 2}, { "VarName": "ipv4_multicast_bridge_M1_multicast_bridge_s_g_hit_ALU1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1_multicast_bridge_s_g_hit_ALU1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1_multicast_bridge_s_g_hit_ALU2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1_multicast_bridge_s_g_hit_ALU2_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2", "X": 2}, { "VarName": "ipv4_multicast_bridge_M2_multicast_bridge_s_g_hit_ALU1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2_multicast_bridge_s_g_hit_ALU1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2_multicast_bridge_s_g_hit_ALU2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2_multicast_bridge_s_g_hit_ALU2_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M3", "X": 2}, { "VarName": "ipv4_multicast_bridge_M3_multicast_bridge_s_g_hit_ALU1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M3_multicast_bridge_s_g_hit_ALU1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M3_multicast_bridge_s_g_hit_ALU2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M3_multicast_bridge_s_g_hit_ALU2_stage1", "X": 1}, { "VarName": "ipv4_multicast_route_M0", "X": 2}, { "VarName": "ipv4_multicast_route_M0_multicast_route_s_g_hit_0_ALU1_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M0_multicast_route_s_g_hit_0_ALU2_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M0_multicast_route_s_g_hit_0_ALU3_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M0_multicast_route_s_g_hit_0_ALU4_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M1", "X": 2}, { "VarName": "ipv4_multicast_route_M1_multicast_route_s_g_hit_0_ALU1_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M1_multicast_route_s_g_hit_0_ALU2_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M1_multicast_route_s_g_hit_0_ALU3_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M1_multicast_route_s_g_hit_0_ALU4_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M2", "X": 2}, { "VarName": "ipv4_multicast_route_M2_multicast_route_s_g_hit_0_ALU1_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M2_multicast_route_s_g_hit_0_ALU2_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M2_multicast_route_s_g_hit_0_ALU3_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M2_multicast_route_s_g_hit_0_ALU4_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M3", "X": 2}, { "VarName": "ipv4_multicast_route_M3_multicast_route_s_g_hit_0_ALU1_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M3_multicast_route_s_g_hit_0_ALU2_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M3_multicast_route_s_g_hit_0_ALU3_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M3_multicast_route_s_g_hit_0_ALU4_stage0", "X": 1}, { "VarName": "sampling_table_M0", "X": 2}, { "VarName": "sampling_table_M0_sampling_ALU1", "X": 1}, { "VarName": "sampling_table_M0_sampling_ALU1_stage1", "X": 1}, { "VarName": "sampling_table_M0_sampling_ALU2", "X": 2}, { "VarName": "sampling_table_M0_sampling_ALU2_stage2", "X": 1}, { "VarName": "ipv4_dest_vtep_M0_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M0_stage1", "X": 1}, { "VarName": "ipv4_dest_vtep_M0_stage2", "X": 1}, { "VarName": "ipv4_dest_vtep_M1_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M1_stage2", "X": 1}, { "VarName": "ipv4_dest_vtep_M2_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M2_stage2", "X": 1}, { "VarName": "ipv4_dest_vtep_M3_stage0", "X": 1}, { "VarName": "ipv4_dest_vtep_M3_stage2", "X": 1}, { "VarName": "ingress_l4_src_port_M0_stage1", "X": 1}, { "VarName": "ingress_l4_src_port_M1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M0_stage2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M1_stage2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2_stage1", "X": 1}, { "VarName": "ipv4_multicast_bridge_M2_stage2", "X": 1}, { "VarName": "ipv4_multicast_bridge_M3_stage1", "X": 1}, { "VarName": "ipv4_multicast_route_M0_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M1_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M2_stage0", "X": 1}, { "VarName": "ipv4_multicast_route_M3_stage0", "X": 1}, { "VarName": "sampling_table_M0_stage1", "X": 1}, { "VarName": "sampling_table_M0_stage2", "X": 1}, { "VarName": "s0_beg", "X": 1}, { "VarName": "s0_end", "X": 2}, { "VarName": "s0_stage1", "X": 1}, { "VarName": "x1", "X": 1}, { "VarName": "x2", "X": 1}, { "VarName": "x3", "X": 1}, { "VarName": "x4", "X": 1}, { "VarName": "x6", "X": 1}, { "VarName": "x8", "X": 1}, { "VarName": "x10", "X": 1}, { "VarName": "x12", "X": 1}, { "VarName": "x14", "X": 1}, { "VarName": "x16", "X": 1}, { "VarName": "x18", "X": 1}, { "VarName": "x20", "X": 1}, { "VarName": "x22", "X": 1}]}
    
    tmp_pkt_pos_dic = {} #key: tmp field name, value: the position they are put
    # update_var_dic = {'T1_A1_ALU1' : 1,
    #             'T1_A1_ALU2' : 2,
    #             'T1_A1_ALU3' : 3,
    #             'T1_A1_ALU4' : 4,
    #             'T1_A1_ALU5' : 5,
    #             'T1_A1_ALU6' : 6}
    table_match_part_dic = {} # key: table name, val: how many match components
    for tbl in table_size_dic:
        table_match_part_dic[tbl] = math.ceil(table_size_dic[tbl] / float(entries_per_table))
    
    # TODO: read from json file
    # turn ILP's allocation output to a dictionary (Only have non-zero value)
    
    var_val_dict = parse_json(ILP_alloc)
    # print(var_val_dict)
    # print("var_val_dict =", var_val_dict)

    # get total number of stages from json output
    if 'cost' in var_val_dict:
        cost = var_val_dict['cost'] + 1 
    else:
        cost = 1
    used_stage = cost

    stage_dic = {}
    for i in range(used_stage):
        stage_dic[i] = len(pkt_fields_def)
    # fill in tmp_pkt_pos_dic
    for tmp_field in tmp_fields_def:
        beg_val = tmp_field + "_beg"
        end_val = tmp_field + "_end"
        # If its value is zero, json will not output it
        if beg_val in var_val_dict:
            beg_stage = var_val_dict[beg_val]
        else:
            beg_stage = 0
        end_stage = var_val_dict[end_val]
        tmp_pkt_pos_dic[tmp_field] = stage_dic[beg_stage]
        # print("beg_stage =",beg_stage)
        # print("end_stage =",end_stage)
        print("stage_dic =", stage_dic)
        for stg in range(beg_stage, end_stage):
            stage_dic[stg] = stage_dic[stg] + 1
    print("tmp_pkt_pos_dic =", tmp_pkt_pos_dic)
    state_var_pos_dic = {} # key: stateful var name; val: the number of PHV containers to store its value
    for stateful_var in state_var_op_dic:
        table_name = state_var_op_dic[stateful_var][0][0]
        action_name = state_var_op_dic[stateful_var][0][1]
        alu_name = state_var_op_dic[stateful_var][0][2]
        var_name = table_name + "_M0_" +  action_name + "_" + alu_name
        stateful_alu_stage = var_val_dict[var_name]

        state_var_pos_dic[stateful_var] = stage_dic[stateful_alu_stage]
        stage_dic[stateful_alu_stage] += 1
        # print("var_name =",var_name,"stateful_alu_stage=",stateful_alu_stage)
    
    print("state_var_pos_dic =",state_var_pos_dic)

    num_of_pkts_in_def = len(pkt_fields_def)
    pkt_container_dic = {} # key: pkt_field, val: container idx

    for tmp_field in tmp_pkt_pos_dic:
        pkt_container_dic[tmp_field] = tmp_pkt_pos_dic[tmp_field]
    for state_var in state_var_pos_dic:
        pkt_container_dic[state_var] = state_var_pos_dic[state_var]
    print("pkt_container_dic =", pkt_container_dic)
    out_str = ""
    # Parse and Deparser (DONE)
    # Part I
    out_str += "Parser 00000" + int_to_bin_str(module_id['Parser'], 3) +\
    "0000000000000001 " + "00000" + int_to_bin_str(module_id['Deparser'], 3) +\
    "0000000000000001\n"
    # Part II
    tmp_str = ""
    curr_pos = 46 # start from 46
    idx_num = 0
    for i in range(num_of_phv):
        if i < num_of_pkts_in_def:
            tmp_str += "000000" # [23:18]
            tmp_str += int_to_bin_str(curr_pos, 9) # [17:9]
            curr_pos += 4
            tmp_str += "10" # all are 32-bit 4B [8:7]
            tmp_str += int_to_bin_str(idx_num, 6)   # [6:1]
            pkt_container_dic[pkt_fields_def[i]] = idx_num
            idx_num += 1
            tmp_str += "1"
            
        else:
            tmp_str += "000000000000000000000000"
    out_str += tmp_str + "\n"
    # print(out_str)
    
    
    used_table_dict = {} # key: stage number; val: list of tables appear in that stage
    used_table_dict = gen_table_stage_alloc(var_val_dict, table_match_part_dic, cost)
    print("used_table_dict =",used_table_dict)
    # print("used_table_dict =", used_table_dict)
    for i in range(used_stage):
        used_table = len(used_table_dict[i])
        for j in range(used_table):
            # For now, we think if more than one match component of a table is in the same stage,
            # then only one of them will be used to execute the match/action rule
            if j > 0 and used_table_dict[i][j] == used_table_dict[i][j - 1]:
                continue
            # KeyExtractConf
            # get Info required (e.g., stage number, match field idx, table number etc.)
            table_name = used_table_dict[i][j] # get it from ILP's output
            print("table_name =", table_name)
            key_extract_str = "KeyExtractConf " + int_to_bin_str(i, 5) + int_to_bin_str(module_id['KeyExtractConf'], 3) +\
                int_to_bin_str(j, 4) + "0000" + "00000001\n"
            match_fields_l = match_field_dic[table_name]
            for k in range(num_of_match_field):
                if k < len(match_fields_l):
                    field_name = match_fields_l[k]
                    key_extract_str += int_to_bin_str(pkt_container_dic[field_name], 6)
                else:
                    key_extract_str += "000000"
            key_extract_str += "11"
            key_extract_str += "000000000"
            key_extract_str += "000000000"
            key_extract_str += "0000\n"
            
            
            # CAMMaskConf
            cam_mask_conf_str = "CAMMaskConf " + int_to_bin_str(i, 5) + int_to_bin_str(module_id['CAMMaskConf'], 3) +\
                int_to_bin_str(j, 4) + "1111" + "00000001\n"
            for k in range(num_of_match_field):
                if k < len(match_fields_l):
                    cam_mask_conf_str += "00000000000000000000000000000000"
                else:
                    cam_mask_conf_str += "11111111111111111111111111111111"
            cam_mask_conf_str += "1"
            cam_mask_conf_str += "0000000\n"
            
            
            # CAMConf
            cam_conf_str = "CAMConf " + int_to_bin_str(i, 5) + int_to_bin_str(module_id['CAMConf'], 3) +\
                int_to_bin_str(j, 4) + "0000" + "00000000\n"
            cam_conf_str += "000000000001"
            for k in range(num_of_match_field):
                if k < len(match_fields_l):
                    field_name = match_fields_l[k]
                    # TODO: consider more than one match action rule
                    # match_action_rule = {'T1' : [({'pkt_0' : 5}, 'A1')]}
                    val = match_action_rule[table_name][0][0][field_name]
                    cam_conf_str += int_to_bin_str(val, 32)
                else:
                    cam_conf_str += int_to_bin_str(0, 32)

            cam_conf_str += "0"
            cam_conf_str += "000\n"
            

            # RAMConf
            ram_conf_str = "RAMConf " + int_to_bin_str(i, 5) + int_to_bin_str(module_id['RAMConf'], 3) +\
                int_to_bin_str(j, 4) + "1111" + "00000000\n"
            # match_action_rule = {'T1' : [({'pkt_0' : 5}, 'A1')]}
            action_name = match_action_rule[table_name][0][1]
            alu_l = action_alu_dic[table_name][action_name]
            # print("alu_l =", alu_l)
            
            
            ram_list = ["0000000000000000000000000000000000000000000000000000000000000000"] * 65
            for k in range(table_match_part_dic[table_name]):
                for alu in alu_l:
                    var_name = "%s_M%s_%s_%s" % (table_name, k, action_name, alu)
                    # print("var_name =",var_name)
                    # find which stage all alus in alu_l are allocated
                    if var_name not in var_val_dict:
                        stage_of_this_alu = 0
                    else:
                        stage_of_this_alu = var_val_dict[var_name]
                    # if one particular alu is allocated in this stage, we should set the configuration
                    if stage_of_this_alu == i:
                        # find which packet field is modified by this alu
                        packet_field = get_modified_pkt(table_name, action_name, alu, pkt_alu_dic)
                        if var_name == "stateful_fw_table_M0_stateful_fw_ALU0":
                            print("packet_field =", packet_field)
                        if packet_field == -1:
                            # TODO: consider the case where the ALU is used to modify tmp field/stateful vars
                            variable_name = table_name + "_" + action_name + "_" + alu
                            print("variable_name =", variable_name)
                            assert variable_name in update_state_dic ,"Not modify fields in definition"
                            # print("stage_dic =",stage_dic)
                            # print("variable_name =", variable_name)
                            # print("i =", i)
                            tmp_str = update_state_dic[variable_name]
                            # print("tmp_str =", tmp_str)
                            # sys.exit(0)
                            for stateful_var in state_var_op_dic:
                                if [table_name, action_name, alu] in state_var_op_dic[stateful_var]:
                                    corresponding_state_name = stateful_var
                                    break
                            print("corresponding_state_name =", corresponding_state_name)
                            print("tmp_str =", tmp_str)
                            ram_list[num_of_phv - 1 - state_var_pos_dic[corresponding_state_name]] = tmp_str
                            stage_dic[i] += 1
                        else:
                            alu_func_name = "%s_%s_%s" % (table_name, action_name, alu)
                            # print("alu_func_name =", alu_func_name)
                            if alu_func_name in update_state_dic:
                                # stateful update and output to PHV
                                tmp_str = update_state_dic[alu_func_name]
                                ram_list[num_of_phv - 1 - pkt_container_dic[packet_field]] = tmp_str
                                continue
                            update_val_dict = update_var_dic[alu_func_name]
                            # TODO generate stateless alu from update_val_dict
                            # {'opcode': 0, 'operand0': 'pkt_0', 'operand1': 'pkt_0', 'operand2': 'pkt_0', 'immediate_operand': 7}
                            opcode = update_val_dict['opcode']
                            # print("update_val_dict =",update_val_dict)
                            # print("opcode =", opcode)
                            if opcode == 0:
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00001110" + int_to_bin_str(pkt_container_dic[packet_field], 6) +\
                                    int_to_bin_str(immediate_operand, 50)
                            elif opcode == 2:
                                operand0 = update_val_dict['operand0']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00001001" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(immediate_operand, 50)
                            elif opcode == 12:
                                print("Come here\n")
                                print("packet_field =", packet_field)
                                # operand0 < operand1
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                tmp_str = "00011100" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(0, 44)
                            elif opcode == 13:
                                operand0 = update_val_dict['operand0']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00011101" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(immediate_operand, 50)
                            elif opcode == 18:
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                tmp_str = "00010011" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(0, 44)
                            elif opcode == 20:
                                operand0 = update_val_dict['operand0']
                                tmp_str = "00000101" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(0, 50)
                            elif opcode == 9:
                                # return (pkt_0 == immediate_operand);
                                operand0 = update_val_dict['operand0']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00010111" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(immediate_operand, 50)
                            elif opcode == 15:
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00010001" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(immediate_operand, 44)
                            elif opcode == 10:
                                #return (pkt_0 >= pkt_1);
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                tmp_str = "00011000" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(0, 44)
                                print("opcode == 10")
                            elif opcode == 4:
                                #return pkt_0 - immediate_operand;
                                operand0 = update_val_dict['operand0']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00000011" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(immediate_operand, 50)
                            elif opcode == 14:
                                #return pkt_0 != 0 ? pkt_1 : pkt_2;
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                operand2 = update_val_dict['operand2']
                                tmp_str = "00010000" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(pkt_container_dic[operand2], 6) + int_to_bin_str(0, 38)
                            elif opcode >= 20:
                                # return (pkt_0 == 0);
                                operand0 = update_val_dict['operand0']
                                tmp_str = "00010111" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(0, 50)
                            elif opcode == 1:
                                #return pkt_0 + pkt_1;
                                operand0 = update_val_dict['operand0']
                                operand1 = update_val_dict['operand1']
                                tmp_str = "00000001" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(pkt_container_dic[operand1], 6) + int_to_bin_str(pkt_container_dic[operand2], 6) + int_to_bin_str(0, 38)
                            elif opcode == 7:
                                #return (pkt_0 != immediate_operand);
                                operand0 = update_val_dict['operand0']
                                immediate_operand = update_val_dict['immediate_operand']
                                tmp_str = "00000101" + int_to_bin_str(pkt_container_dic[operand0], 6) + int_to_bin_str(immediate_operand, 50)
                            else:
                                print("opcode =", opcode)
                                assert False, "not yet support"     

                            ram_list[num_of_phv - 1 - pkt_container_dic[packet_field]] = tmp_str

            # Add to ram_conf_str
            for content in ram_list:
                ram_conf_str += content
            ram_conf_str += "\n"
            
            #TODO: only add int out_str if there is some ALU in ram_conf_str is used
            if valid_ram_list(ram_list):
                if i == 3:
                    print("stage no.3 comes here")
                out_str += key_extract_str
                out_str += cam_mask_conf_str
                out_str += cam_conf_str
                out_str += ram_conf_str
            

    if out_str[-1] == '\n':
        out_str = out_str[:-1]
    print(out_str)

if __name__ == '__main__':
    main(sys.argv)