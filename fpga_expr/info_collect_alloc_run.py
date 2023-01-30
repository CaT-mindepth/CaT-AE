import ILP_solver

import sys
import json


'''
DONE pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4', 'pkt_5', 'pkt_6', 'pkt_7', 'pkt_8', 'pkt_9', 'pkt_10', 'pkt_11', 'pkt_12', 'pkt_13']
DONE tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3'] # all temporary variables
DONE stateful_var_def = ['s0'] # all stateful variables
DONE table_act_dic = {'T1':['A1','A2'], 'T2':['A1']} #key: table name, val: list of actions
DONE table_size_dic = {'T1':512, 'T2':1} #key: table name, val: table size
DONE action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3'], 'A2': ['ALU1','ALU2']} } #key: table name, val: dictionary whose key is action name and whose value is list of alus
    #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
DONE alu_dep_dic = {'T2': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
DONE pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']],
                   'pkt_1':[['T1','A1','ALU2']],
                   'pkt_3':[['T1','A1','ALU3']],
                   'pkt_5':[['T1','A2','ALU1']],
                   'pkt_6':[['T1','A2','ALU2']],
                   'pkt_12' :[['T2','A1','ALU1']],
                   'pkt_13' :[['T2','A1','ALU5']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
DONE tmp_alu_dic = {'tmp_0':[['T2','A1','ALU2'],['T2','A1','ALU7']],
                    'tmp_1':[['T2','A1','ALU6'],['T2','A1','ALU3'],['T2','A1','ALU7']],
                    'tmp_2':[['T2','A1','ALU7'],['T2','A1','ALU5']],
                    'tmp_3':[['T2','A1','ALU4'],['T2','A1','ALU5']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
    DONE state_alu_dic = {'s0':[['T2','A1','ALU3'], ['T2','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
    DONE match_dep = [['T1','T2']] #list of list, for each pari [T1, T2], T2 has match dependency on T1

    DONE action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
    DONE reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
'''

'''Find the key name with the format: no. 1 key is meta.sample_key; with match type exact;'''
def find_key_name(l):
    for i in range(len(l)):
        if l[i] == 'key' and l[i + 1] == 'is':
            return l[i + 2]
'''Find all actions for table with the format: table action list is { set_pkt; }'''
def find_actions(s):
    action_list = []
    new_s = s.split('{')[-1].split('}')[0]
    new_list = new_s.split(' ')
    for v in new_list:
        if v.find(';') != -1:
            action_name = v[:-1]
            action_list.append(action_name)
    return action_list

def main(argv):
    filename = "/tmp/output_from_p4c.txt"
    # collect all table names
    f = open(filename, 'r')

    table_info_flag = 0
    action_info_flag = 0
    struct_info_flag = 0

    table_size_dic = {}
    table_act_dic = {}
    pkt_fields_def = []
    stateful_var_def = []

    match_dep = []
    action_dep = []
    reverse_dep = []
    successor_dep = []

    while True:
        line = f.readline()
        if not line:
            break
        if line.find("Table Info") != -1:
            table_info_flag = 1
            action_info_flag = 0
            struct_info_flag = 0
            table_name = ""
            key_name_l = []
            table_size = 0
            act_of_table = []
        elif line.find("Action Info") != -1:
            table_info_flag = 0
            struct_info_flag = 0
            action_info_flag = 1
            while 1:
                line = f.readline()
                if line.find("value_str =") != -1:
                    s = line.strip().split(' ')[-1]
                    stateful_var = s.split('.')[0]
                    if stateful_var not in stateful_var_def:
                        stateful_var_def.append(stateful_var)
                if line.find("Domino program") != -1:
                    domino_program = ""
                    while 1:
                        line = f.readline()
                        if not line or line == "\n":
                            break
                        else:
                            domino_program += line
                    break
            action_info_flag = 0
            print("Domino program =", domino_program)
        elif line.find("Struct and Header Info") != -1:
            table_info_flag = 0
            action_info_flag = 0
            struct_info_flag = 1
        else:
            if table_info_flag == 1:
                line_v = line.strip()
                if line_v.find("table name is") != -1:
                    table_name = line_v.split(' ')[-1]
                elif line_v.find("with match type exact") != -1:
                    l = line_v.split(' ')
                    key_name_l.append(find_key_name(l))
                elif line_v.find("table size is") != -1:
                    l = line_v.split(' ')
                    table_size = int(l[-1])
                elif line_v.find("table action list") != -1:
                    act_of_table = find_actions(line_v)
                    table_size_dic[table_name] = table_size
                    table_act_dic[table_name] = act_of_table
            elif struct_info_flag == 1:
                # For now, we assume all variables are bit<32>
                if line.find("bit<") != -1:
                    pkt_name = line.split(' ')[1]
                    pkt_fields_def.append(pkt_name)
    f.close()
    f = open("/home/xiangyug/CaT-AE/p4_input_program/sampling.json", 'r')
    contents = f.read()
    table_info = json.loads(contents)

    stateful_alu_l = table_info["stateful_alus"]
    stateless_alu_l = table_info["stateless_alus"]
    alu_dependencies = table_info["alu_dependencies"]

    # action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3']}
    action_alu_dic = {}
    for table in table_size_dic:
        action_alu_dic[table] = {}
        for action in table_act_dic[table]:
            action_alu_dic[table][action] = []
            num_of_alu = len(stateful_alu_l) + len(stateless_alu_l)
            for i in range(num_of_alu):
                action_alu_dic[table][action].append('ALU' + str(i))
    # print("action_alu_dic =", action_alu_dic)
    # print(table_info)
    # alu_dep_dic = {'T2':{'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
    #                            ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
    alu_dep_dic = {}
    for table in table_size_dic:
        alu_dep_dic[table] = {}
        # Assume now we only have one action per table
        for action in table_act_dic[table]:
            alu_dep_dic[table][action] = []
            dep_l = table_info["alu_dependencies"]
            for edge in dep_l:
                ALU1 = "ALU" + str(edge[0])
                ALU2 = "ALU" + str(edge[1])
                alu_dep_dic[table][action].append([ALU1, ALU2])
    # tmp_alu_dic = {'tmp_0':[['T2','A1','ALU2'],['T2','A1','ALU7']]
    # pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']]}
    # tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3']
    pkt_alu_dic = {}
    tmp_fields_def = []
    for table in table_size_dic:
        for action in table_act_dic[table]:
            for pkt in pkt_fields_def:
                pkt_alu_dic[pkt] = []
            for dic in stateless_alu_l:
                out_var = dic["result"]
                if out_var[:2] == 'p_':
                    while out_var[-1] >= '1' and out_var[-1] <= '9':
                        out_var = out_var[:-1]
                    out_var = out_var[2:]
                    id = dic["id"]
                    l = [table, action, "ALU"+str(id)]
                    pkt_alu_dic[pkt].append(l)
                else:
                    tmp_fields_def.append(out_var) 
    # print("pkt_alu_dic =", pkt_alu_dic)
    tmp_alu_dic = {}
    for table in table_size_dic:
        for action in table_act_dic[table]:
            for pkt in tmp_fields_def:
                tmp_alu_dic[pkt] = []
            for dic in stateless_alu_l:
                out_var = dic["result"]
                if out_var in tmp_fields_def:
                    id = dic["id"]
                    l = [table, action, "ALU"+str(id)]
                    tmp_alu_dic[pkt].append(l)
    # print("tmp_alu_dic =", tmp_alu_dic)
        
    # state_alu_dic = {'s0':[['T2','A1','ALU3'], ['T2','A1','ALU4']]}
    state_alu_dic = {}
    for stateful_var in stateful_var_def:
        state_alu_dic[stateful_var] = []
        for table in table_size_dic:
            for action in table_act_dic[table]:
                for dic in stateful_alu_l:
                    output_l = dic["outputs"]
                    if stateful_var in output_l:
                        id = dic["id"]
                        l = [table, action, "ALU"+str(id)]
                        state_alu_dic[stateful_var].append(l)
                for dic in stateless_alu_l:
                    flag = 0
                    # Here, we assume that stateful var's name only occurs once
                    for v in [dic["operand0"], dic["operand1"], dic["operand2"]]:
                        if v.find(stateful_var) != -1:
                            flag = 1
                            break
                    if flag == 1:
                        id = dic["id"]
                        l = [table, action, "ALU"+str(id)]
                        state_alu_dic[stateful_var].append(l)

    # print("state_alu_dic =", state_alu_dic)
    # print("alu_dep_dic =", alu_dep_dic)
    # print("table_size_dic =", table_size_dic)
    # print("table_act_dic =", table_act_dic)
    # print("pkt_fields_def =", pkt_fields_def)
    # print("stateful_var_def =", stateful_var_def)
    # TODO: given we are only testing the output for one program, all table dependencies does not exist
    # print("match_dep =", match_dep)
    # print("action_dep =", action_dep)
    # print("reverse_dep =", reverse_dep)
    # print("successor_dep =", successor_dep)

    # Use ILP solver to solve the integer linear programming problem
    opt = True # Set ILP with Gurobi in optimal mode as the default
    ILP_solver.solve_ILP(pkt_fields_def, tmp_fields_def, stateful_var_def, 
    table_act_dic, table_size_dic, action_alu_dic, alu_dep_dic,
    pkt_alu_dic, tmp_alu_dic, state_alu_dic,
    match_dep, action_dep, successor_dep, reverse_dep, opt)

if __name__ == '__main__':
    main(sys.argv)