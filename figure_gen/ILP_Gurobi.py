import sys

import math

import gurobipy as gp
from gurobipy import GRB

num_of_entries_per_table = 256
num_of_alus_per_stage = 64
num_of_table_per_stage = 8
num_of_stages = 12

def solve_ILP(pkt_fields_def, tmp_fields_def, stateful_var_def, 
    table_act_dic, table_size_dic, action_alu_dic, alu_dep_dic,
    pkt_alu_dic, tmp_alu_dic, state_alu_dic,
    match_dep, action_dep, successor_dep, reverse_dep, opt = True):

    global_cnt = 0
    num_of_fields = len(pkt_fields_def)

    m = gp.Model("ILP")
    cost = m.addVar(name='cost', vtype=GRB.INTEGER)

    '''Build a dict showing how many match components per table'''
    table_match_dic = {} # key: table name, val: number of match components, {T1: 2}
    for table in  table_size_dic:
        size = table_size_dic[table]
        table_match_dic[table] = math.ceil(float(size) / num_of_entries_per_table)

    alu_components_var = []
    match_components_var = []
    alu_loc_var_vec = []

    for table in table_size_dic:
        num_of_match_components = table_match_dic[table]
        for i in range(num_of_match_components):
            match_components_var.append(m.addVar(name="%s_M%s" % (table, i), vtype=GRB.INTEGER))
            list_of_actions = table_act_dic[table]
            for action in list_of_actions:
                alu_list = action_alu_dic[table][action]
                for alu in alu_list:
                    alu_components_var.append(m.addVar(name="%s_M%s_%s_%s" % (table, i, action, alu), vtype=GRB.INTEGER))
                    tmp_l = []
                    for j in range(num_of_stages):
                        tmp_l.append(m.addVar(name="%s_M%s_%s_%s_stage%s" % (table, i, action, alu, j), vtype=GRB.BINARY))
                    alu_loc_var_vec.append(tmp_l) 
    
    # Add prelimianry constraints >=0
    for var in match_components_var:
        m.addConstr(var >= 0)
        m.addConstr(cost >= var)
    for var in alu_components_var:
        m.addConstr(var >= 0)
        m.addConstr(cost >= var)
    '''it is necessary to update model before later processing
    ref: https://support.gurobi.com/hc/en-us/community/posts/360059768191-GurobiError-No-variable-names-available-to-index
    '''
    m.update()

    # Add alu-level dependency within an action
    for table in alu_dep_dic:
        num_of_match_components = table_match_dic[table]
        for i in range(num_of_match_components):
            for action in alu_dep_dic[table]:
                for pair in alu_dep_dic[table][action]:
                    alu1 = pair[0]
                    alu2 = pair[1]
                    alu1_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu1))
                    alu2_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu2))
                    m.addConstr(alu1_var <= alu2_var - 1) # alu1_var < alu2_var

    # Add table-level dependency
    for pair in match_dep:
        table1 = pair[0]
        table2 = pair[1]
        table1_size = table_match_dic[table1]
        table2_size = table_match_dic[table2]
        for i in range(table1_size):
            for j in range(table2_size):
                for table1_act in action_alu_dic[table1]:
                    for table2_act in action_alu_dic[table2]:
                        for table1_act_alu in action_alu_dic[table1][table1_act]:
                            for table2_act_alu in action_alu_dic[table2][table2_act]:
                                table1_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table1, i, table1_act, table1_act_alu))
                                table2_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table2, j, table2_act, table2_act_alu))
                                m.addConstr(table1_alu_var <= table2_alu_var - 1)
    for pair in action_dep:
        table1 = pair[0]
        table2 = pair[1]
        table1_size = table_match_dic[table1]
        table2_size = table_match_dic[table2]
        for i in range(table1_size):
            for j in range(table2_size):
                for table1_act in action_alu_dic[table1]:
                    for table2_act in action_alu_dic[table2]:
                        for table1_act_alu in action_alu_dic[table1][table1_act]:
                            for table2_act_alu in action_alu_dic[table2][table2_act]:
                                table1_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table1, i, table1_act, table1_act_alu))
                                table2_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table2, j, table2_act, table2_act_alu))
                                m.addConstr(table1_alu_var <= table2_alu_var - 1)

    for pair in reverse_dep:
        table1 = pair[0]
        table2 = pair[1]
        table1_size = table_match_dic[table1]
        table2_size = table_match_dic[table2]
        for i in range(table1_size):
            for j in range(table2_size):
                for table1_act in action_alu_dic[table1]:
                    for table2_act in action_alu_dic[table2]:
                        for table1_act_alu in action_alu_dic[table1][table1_act]:
                            for table2_act_alu in action_alu_dic[table2][table2_act]:
                                table1_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table1, i, table1_act, table1_act_alu))
                                table2_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table2, j, table2_act, table2_act_alu))
                                m.addConstr(table1_alu_var <= table2_alu_var)
    
    for pair in successor_dep:
        table1 = pair[0]
        table2 = pair[1]
        table1_size = table_match_dic[table1]
        table2_size = table_match_dic[table2]
        for i in range(table1_size):
            for j in range(table2_size):
                for table1_act in action_alu_dic[table1]:
                    for table2_act in action_alu_dic[table2]:
                        for table1_act_alu in action_alu_dic[table1][table1_act]:
                            for table2_act_alu in action_alu_dic[table2][table2_act]:
                                table1_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table1, i, table1_act, table1_act_alu))
                                table2_alu_var = m.getVarByName("%s_M%s_%s_%s" % (table2, j, table2_act, table2_act_alu))
                                m.addConstr(table1_alu_var <= table2_alu_var)

    # All alus must be allocated to one and only one stage
    for alu_vec in alu_loc_var_vec:
        m.addConstr(sum(alu_vec) == 1)

    # restrict the number of tables used within a stage should be smaller than or equal to number of tables per stage    
    table_loc_var_vec = []
    for table in table_size_dic:
        num_of_match_components = table_match_dic[table]
        for i in range(num_of_match_components):
            tmp_list = []
            for j in range(num_of_stages):
                tmp_list.append(m.addVar(name="%s_M%s_stage%s" % (table, i, j), vtype=GRB.BINARY))
            table_loc_var_vec.append(tmp_list)
    m.update()
    for table in table_size_dic:
        for i in range(table_match_dic[table]):
            match_var = m.getVarByName("%s_M%s" % (table, i))
            action_list = table_act_dic[table] 
            for action in action_list:
                alu_list = action_alu_dic[table][action]
                for alu in alu_list:
                    alu_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu))
                    for j in range(num_of_stages):
                        alu_stage_var = m.getVarByName("%s_M%s_%s_%s_stage%s" % (table, i, action, alu, j))
                        match_var_stage = m.getVarByName("%s_M%s_stage%s" % (table, i, j))
                        # m.addConstr(alu_stage_var <= match_var_stage)
                        m.addConstr((alu_stage_var == 1) >> (match_var_stage == 1))
                        # TODO: change to ILP constraints
                        m.addConstr((alu_stage_var == 1) >> (alu_var == j))
                        m.addConstr((match_var_stage == 1) >> (match_var >= j))

    table_loc_var_vec_transpose = [[table_loc_var_vec[i][j] for i in range(len(table_loc_var_vec))] for j in range(len(table_loc_var_vec[0]))]
    for i in range(len(table_loc_var_vec_transpose)):
        m.addConstr(sum(table_loc_var_vec_transpose[i]) <= num_of_table_per_stage)

    # Use no more than available ALUs per stage
    tmp_state_field_loc_vec = []
    for tmp_field in tmp_fields_def:
        m.addVar(name="%s_beg" % tmp_field) # Beg is the stage number it is written. It is unique because of SSA
        m.addVar(name="%s_end" % tmp_field) # End is >= the stage number it is last read.
        tmp_list = []
        for i in range(num_of_stages):
            tmp_list.append(m.addVar(name="%s_stage%s" % (tmp_field, i), vtype=GRB.BINARY))
        tmp_state_field_loc_vec.append(tmp_list)
    m.update()

    for tmp_field in tmp_fields_def:
        beg_var = m.getVarByName("%s_beg" % tmp_field)
        end_var = m.getVarByName("%s_end" % tmp_field)
        m.addConstr(beg_var >= 0)
        m.addConstr(beg_var <= num_of_stages - 1)
        m.addConstr(end_var >= 0)
        m.addConstr(end_var <= num_of_stages - 1)
        # m.addConstr(beg_var <= end_var - 1)
        for j in range(len(tmp_alu_dic[tmp_field])):
            mem = tmp_alu_dic[tmp_field][j]
            table = mem[0]
            action = mem[1]
            alu = mem[2]
            if j == 0:
                # the ALU that writes tmp fields
                for i in range(table_match_dic[table]):
                    alu_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu))
                    m.addConstr(beg_var == alu_var)
                    m.addConstr(beg_var + 1 <= end_var)
            else:
                # the ALUs that read tmp fields
                for i in range(table_match_dic[table]):
                    alu_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu))
                    m.addConstr(alu_var <= end_var)

    for tmp_field in tmp_fields_def:
        beg_var = m.getVarByName("%s_beg" % tmp_field)
        end_var = m.getVarByName("%s_end" % tmp_field)
        for i in range(num_of_stages):
            # global global_cnt 
            new_var = m.addVar(name='x%s' % global_cnt, vtype=GRB.BINARY)
            # beg <= i < end -> allocate one alu for this tmp field
            stage_var = m.getVarByName("%s_stage%s" % (tmp_field, i))
            m.addGenConstrIndicator(new_var, True, beg_var <= i)
            m.addGenConstrIndicator(new_var, False, beg_var >= i + 1)
            global_cnt += 1
            new_var1 = m.addVar(name='x%s' % global_cnt, vtype=GRB.BINARY)
            m.addGenConstrIndicator(new_var1, True, end_var >= i + 1)
            m.addGenConstrIndicator(new_var1, False, end_var <= i)
            m.addConstr(stage_var == new_var1 * new_var)
            global_cnt += 1

    for state_var in stateful_var_def:
        m.addVar(name="%s_beg" % state_var)
        m.addVar(name="%s_end" % state_var)
        tmp_list = []
        for i in range(num_of_stages):
            tmp_list.append(m.addVar(name="%s_stage%s" % (state_var, i), vtype=GRB.BINARY))
        tmp_state_field_loc_vec.append(tmp_list)
    m.update()
    for state_var in stateful_var_def:
        beg_var = m.getVarByName("%s_beg" % state_var) # Beg is the stage number for stateful ALU
        end_var = m.getVarByName("%s_end" % state_var) # End is >= the stage number it is last read.
        m.addConstr(beg_var >= 0)
        m.addConstr(beg_var <= num_of_stages - 1)
        m.addConstr(end_var >= 0)
        m.addConstr(end_var <= num_of_stages - 1)

        for j in range(len(state_alu_dic[state_var])):
            mem = state_alu_dic[state_var][j]
            table = mem[0]
            action = mem[1]
            alu = mem[2]
            if j == 0:
                for i in range(table_match_dic[table]):
                    alu_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu))
                    m.addConstr(beg_var == alu_var)
                    m.addConstr(beg_var + 1 <= end_var)
            else:
                for i in range(table_match_dic[table]):
                    alu_var = m.getVarByName("%s_M%s_%s_%s" % (table, i, action, alu))
                    m.addConstr(alu_var <= end_var)
        
        for state_var in stateful_var_def:
            beg_var = m.getVarByName("%s_beg" % state_var)
            end_var = m.getVarByName("%s_end" % state_var)
            for i in range(num_of_stages):
                # beg <= i < end -> allocate one alu for this stateful var
                new_var = m.addVar(name='x%s' % global_cnt, vtype=GRB.BINARY)
                stage_var = m.getVarByName("%s_stage%s" % (state_var, i))
                m.addGenConstrIndicator(new_var, True, beg_var <= i)
                m.addGenConstrIndicator(new_var, False, beg_var >= i + 1)
                global_cnt += 1
                new_var1 = m.addVar(name='x%s' % global_cnt, vtype=GRB.BINARY)
                m.addGenConstrIndicator(new_var1, True, end_var >= i + 1)
                m.addGenConstrIndicator(new_var1, False, end_var <= i)
                m.addConstr(stage_var == new_var1 * new_var)
                global_cnt += 1

    m.update()
    if len(tmp_state_field_loc_vec) > 0:
        tmp_state_field_loc_vec_transpose = [[tmp_state_field_loc_vec[i][j] for i in range(len(tmp_state_field_loc_vec))] for j in range(len(tmp_state_field_loc_vec[0]))]
        for i in range(len(tmp_state_field_loc_vec_transpose)):
            m.addConstr(sum(tmp_state_field_loc_vec_transpose[i]) <= num_of_alus_per_stage - num_of_fields)

    '''Start solving the ILP optimization problem'''
    if opt == True:
        m.setObjective(cost, GRB.MINIMIZE)
        print("Solving optimization problem")
    else:
        m.setObjective(1, GRB.MINIMIZE)
        print("Solving satisfiable problem")
    m.update()
    # print("-------------num of variable =", m.getVars())
    # sys.exit(0)
    m.optimize()
    if m.status == GRB.OPTIMAL: 
        print("Following is the result we want:*****************\n\n\n")   
        # print('Optimal objective: %g (zero index)' % m.objVal)
        # collect all variables that we care about their output
        var_l = []
        for table in table_size_dic:
            for i in range(table_match_dic[table]):
                for j in range(num_of_stages):
                    match_str = "%s_M%s_stage%s" % (table, i, j)
                    var_l.append(match_str)
                action_list = table_act_dic[table] 
                for action in action_list:
                    alu_list = action_alu_dic[table][action]
                    for alu in alu_list:
                        alu_str = "%s_M%s_%s_%s" % (table, i, action, alu)
                        var_l.append(alu_str)
        for tmp_field in tmp_fields_def:
            beg_str = "%s_beg" % tmp_field
            end_str = "%s_end" % tmp_field
            var_l.append(beg_str)
            var_l.append(end_str)
        for v in m.getVars():
            # if v.varName != 'cost' and v.varName.find('stage') == -1:
            # if v.varName in var_l or v.varName == 'cost':
            #     print('%s %g' % (v.varName, v.x))
            if v.varName == 'cost':
                print('Total number of stages used is', int(v.x) + 1)

        # print("************************************************")
        # print(m.getJSONSolution())
    else:
        print("Sad")


def main(argv):
    if len(sys.argv) != 3:
        print("Usage:", sys.argv[0], "<mode (either Optimal or Feasible)> <candidate number (1-24)>")
        exit(1)
    else:
        mode = sys.argv[1]
        candidate = int(sys.argv[2])
        assert candidate >= 1 and candidate <= 24, "The candidate number should be between 1 and 24"
        assert mode == "Optimal" or mode == "Feasible", "the mode should be either Optimal or Feasible"
    if mode == "Optimal":
        opt = True
    else:
        opt = False
    if candidate == 1:
        '''*****************test case 1: stateful_fw*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4']
        tmp_fields_def = ['tmp_0','tmp1','tmp2','tmp3'] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'T1':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                    ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
        pkt_alu_dic = {'pkt_3':[['T1','A1','ALU1']], 
                        'pkt_4':[['T1','A1','ALU5']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU2'],['T1','A1','ALU7']],
                        'tmp1':[['T1','A1','ALU6'],['T1','A1','ALU3'],['T1','A1','ALU7']],
                        'tmp2':[['T1','A1','ALU7'],['T1','A1','ALU5']],
                        'tmp3':[['T1','A1','ALU4'],['T1','A1','ALU5']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T1','A1','ALU3'],['T1','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 2:
        '''*****************test case 2: blue_increase*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2'] # all packet fields
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0','s1'] # all stateful variables

        table_act_dic = {'T1':['A1']} # key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3','ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU2'], ['ALU2','ALU3'], ['ALU3','ALU4']]}}

        pkt_alu_dic = {'pkt_1':[['T1','A1','ALU1']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU3'],['T1','A1','ALU4']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        state_alu_dic = {'s0':[['T1','A1','ALU2'],['T1','A1','ALU3']],
                        's1':[['T1','A1','ALU4']]} #key: packet field in def, val: a list of list of size 3, ['table name', 'action name', 'alu name'], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 3:
        '''*****************test case 3: marple_new*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1'] # all packet fields
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables
        table_act_dic = {'T1':['A1']} # key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU2']]}}
        pkt_alu_dic = {'pkt_1':[['T1','A1','ALU2']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        state_alu_dic = {'s0':[['T1','A1','ALU1'],['T1','A1','ALU2']]
                        } #key: packet field in def, val: a list of list of size 3, ['table name', 'action name', 'alu name'], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 4:
        '''*****************test case 4: sampling*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1'] # all packet fields
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'T1':['A1']} # key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU2']]}}

        pkt_alu_dic = {'pkt_1':[['T1','A1','ALU2']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        state_alu_dic = {'s0':[['T1','A1','ALU1'],['T1','A1','ALU2']]} #key: packet field in def, val: a list of list of size 3, ['table name', 'action name', 'alu name'], the first member is the ALU modifies tmp field and the others are ALUs that read from the tmp field
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 5:
        '''*****************test case 5: flowlets*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3']
        tmp_fields_def = ['tmp_0','tmp_1'] # all temporary variables
        stateful_var_def = ['s0', 's1'] # all stateful variables

        table_act_dic = {'T1':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3','ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU3'], ['ALU2','ALU3'], ['ALU3','ALU4']]}}
        pkt_alu_dic = {'pkt_3':[['T1','A1','ALU4']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU2'],['T1','A1','ALU3']],
                        'tmp_1':[['T1','A1','ALU3'],['T1','A1','ALU4']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T1','A1','ALU1'],['T1','A1','ALU3']],
                        's1':[['T1','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 6:
        '''*****************test case 6: rcp*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2']
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2'] # all stateful variables

        table_act_dic = {'T1':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3','ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU3'], ['ALU1','ALU4']]}}
        pkt_alu_dic = {} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU1'],['T1','A1','ALU3'],['T1','A1','ALU4']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T1','A1','ALU2']],
                        's1':[['T1','A1','ALU3']],
                        's2':[['T1','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 7:
        '''*****************test case 7: learn_filter*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1']
        tmp_fields_def = ['tmp_0','tmp_1'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2'] # all stateful variables

        table_act_dic = {'T1':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU4'], ['ALU2','ALU5'], ['ALU3','ALU5'], ['ALU4','ALU6'], ['ALU5','ALU6']]}}
        pkt_alu_dic = {'pkt_1':[['T1','A1','ALU6']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU5'],['T1','A1','ALU6']],
                        'tmp_1':[['T1','A1','ALU4'],['T1','A1','ALU6']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T1','A1','ALU1'],['T1','A1','ALU4']],
                        's1':[['T1','A1','ALU2'],['T1','A1','ALU5']],
                        's2':[['T1','A1','ALU3'],['T1','A1','ALU5']]
                        } #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 8:
        '''*****************test case 8: marple_tcp*****************'''
        pkt_fields_def = ['pkt_0', 'pkt_1']
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0', 's1'] # all stateful variables

        table_act_dic = {'T1':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T1': {'A1': [['ALU1','ALU2'], ['ALU2','ALU3']]}}
        pkt_alu_dic = {} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T1','A1','ALU2'],['T1','A1','ALU3']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T1','A1','ALU1'],['T1','A1','ALU2']],
                        's1':[['T1','A1','ALU3']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
        '''*****************test case 9: ingress_port_mapping + stateful_fw_T /home/xiangyug/benchmarks/switch_p4_benchmarks/test_benchmarks/benchmark1.txt*****************
        elif candidate == 9:
        
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4', 'pkt_5', 'pkt_6']
        tmp_fields_def = ['tmp_0','tmp1','tmp2','tmp3'] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'T1':['A1'], 'T2':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':288, 'T2':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2']},
                        'T2': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T2': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                    ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
        pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']],
                    'pkt_1':[['T1','A1','ALU2']],
                    'pkt_5':[['T2','A1','ALU1']],
                    'pkt_6':[['T2','A1','ALU5']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T2','A1','ALU2'],['T2','A1','ALU7']],
                        'tmp1':[['T2','A1','ALU6'],['T2','A1','ALU3'],['T2','A1','ALU7']],
                        'tmp2':[['T2','A1','ALU7'],['T2','A1','ALU5']],
                        'tmp3':[['T2','A1','ALU4'],['T2','A1','ALU5']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T2','A1','ALU3'], ['T2','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['T1','T2']] #list of list, for each pari [T1, T2], T2 has match dependency on T1

        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
        elif candidate == 10:
        *****************test case 10: validate_outer_ipv4_packet + stateful_fw_T /home/xiangyug/benchmarks/switch_p4_benchmarks/test_benchmarks/benchmark2.txt*****************
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4', 'pkt_5', 'pkt_6', 'pkt_7', 'pkt_8', 'pkt_9', 'pkt_10', 'pkt_11', 'pkt_12', 'pkt_13']
        tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3'] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'T1':['A1','A2'], 'T2':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':512, 'T2':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2','ALU3'], 'A2': ['ALU1','ALU2']},
                        'T2': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T2': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                    ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
        pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']],
                    'pkt_1':[['T1','A1','ALU2']],
                    'pkt_3':[['T1','A1','ALU3']],
                    'pkt_5':[['T1','A2','ALU1']],
                    'pkt_6':[['T1','A2','ALU2']],
                    'pkt_12' :[['T2','A1','ALU1']],
                    'pkt_13' :[['T2','A1','ALU5']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T2','A1','ALU2'],['T2','A1','ALU7']],
                        'tmp_1':[['T2','A1','ALU6'],['T2','A1','ALU3'],['T2','A1','ALU7']],
                        'tmp_2':[['T2','A1','ALU7'],['T2','A1','ALU5']],
                        'tmp_3':[['T2','A1','ALU4'],['T2','A1','ALU5']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T2','A1','ALU3'], ['T2','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['T1','T2']] #list of list, for each pari [T1, T2], T2 has match dependency on T1

        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
        elif candidate == 11:
        *****************test case 11: ingress_port_mapping + validate_outer_ipv4_packet + stateful_fw_T /home/xiangyug/benchmarks/switch_p4_benchmarks/test_benchmarks/benchmark3.txt*****************
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4', 'pkt_5', 'pkt_6', 'pkt_7', 'pkt_8', 'pkt_9', 'pkt_10', 'pkt_11', 'pkt_12', 'pkt_13',
                        'pkt_14', 'pkt_15', 'pkt_16']
        tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3'] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'T1':['A1'], 'T2':['A1','A2'], 'T3':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':288, 'T2':512, 'T3':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2']},
                        'T2': {'A1' : ['ALU1','ALU2','ALU3'], 'A2': ['ALU1','ALU2']},
                        'T3': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T3': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                    ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]}}
        pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']],
                    'pkt_1':[['T1','A1','ALU2']],
                    'pkt_3':[['T2','A1','ALU1']],
                    'pkt_4':[['T2','A1','ALU2']],
                    'pkt_6':[['T2','A1','ALU3']],
                    'pkt_8':[['T2','A2','ALU1']],
                    'pkt_9':[['T2','A2','ALU2']],
                    'pkt_15' :[['T3','A1','ALU1']],
                    'pkt_16' :[['T3','A1','ALU5']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T3','A1','ALU2'],['T3','A1','ALU7']],
                        'tmp_1':[['T3','A1','ALU6'],['T3','A1','ALU3'],['T3','A1','ALU7']],
                        'tmp_2':[['T3','A1','ALU7'],['T3','A1','ALU5']],
                        'tmp_3':[['T3','A1','ALU4'],['T3','A1','ALU5']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T3','A1','ALU3'], ['T3','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['T1','T3']] #list of list, for each pari [T1, T2], T2 has match dependency on T1

        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
        elif candidate == 12:
        *****************test case 12: ingress_port_mapping + validate_outer_ipv4_packet +
                                        stateful_fw_T + blue_increase /home/xiangyug/benchmarks/switch_p4_benchmarks/test_benchmarks/benchmark4.txt*****************
        pkt_fields_def = ['pkt_0', 'pkt_1', 'pkt_2', 'pkt_3', 'pkt_4', 'pkt_5', 'pkt_6', 'pkt_7', 'pkt_8', 'pkt_9', 'pkt_10', 'pkt_11', 'pkt_12', 'pkt_13',
                        'pkt_14', 'pkt_15', 'pkt_16', 'pkt_17', 'pkt_18']

        tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3', 'tmp_4'] # all temporary variables
        stateful_var_def = ['s0','s1','s2'] # all stateful variables

        table_act_dic = {'T1':['A1'], 'T2':['A1','A2'], 'T3':['A1'], 'T4':['A1']} #key: table name, val: list of actions
        table_size_dic = {'T1':288, 'T2':512, 'T3':1, 'T4':1} #key: table name, val: table size
        action_alu_dic = {'T1': {'A1' : ['ALU1','ALU2']},
                        'T2': {'A1' : ['ALU1','ALU2','ALU3'], 'A2': ['ALU1','ALU2']},
                        'T3': {'A1' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                        'T4': {'A1' : ['ALU1', 'ALU2', 'ALU3', 'ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'T3': {'A1': [['ALU2','ALU7'], ['ALU6','ALU3'], ['ALU6','ALU7'],
                                    ['ALU3','ALU4'], ['ALU4','ALU5'], ['ALU7','ALU5']]},
                    'T4': {'A1': [['ALU1', 'ALU2'], ['ALU2', 'ALU3'], ['ALU3', 'ALU4']]}}
        pkt_alu_dic = {'pkt_0':[['T1','A1','ALU1']],
                    'pkt_1':[['T1','A1','ALU2']],
                    'pkt_3':[['T2','A1','ALU1']],
                    'pkt_4':[['T2','A1','ALU2']],
                    'pkt_6':[['T2','A1','ALU3']],
                    'pkt_8':[['T2','A2','ALU1']],
                    'pkt_9':[['T2','A2','ALU2']],
                    'pkt_15' :[['T3','A1','ALU1']],
                    'pkt_16' :[['T3','A1','ALU5']],
                    'pkt_17' :[['T4','A1','ALU3']]} #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['T3','A1','ALU2'],['T3','A1','ALU7']],
                        'tmp_1':[['T3','A1','ALU6'],['T3','A1','ALU3'],['T3','A1','ALU7']],
                        'tmp_2':[['T3','A1','ALU7'],['T3','A1','ALU5']],
                        'tmp_3':[['T3','A1','ALU4'],['T3','A1','ALU5']],
                        'tmp_4':[['T4','A1','ALU3'], ['T4','A1','ALU4']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['T3','A1','ALU3'], ['T3','A1','ALU4']],
                        's1':[['T4','A1','ALU2'], ['T4','A1','ALU3']],
                        's2':[['T4','A1','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['T1','T3'], ['T2','T4']] #list of list, for each pari [T1, T2], T2 has match dependency on T1

        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        successor_dep = []
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
        '''
    elif candidate == 9:
        # benchmark 1 0m0.810s, 0m1.805s
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0', 's1'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'marple_tcp_nmo_table':['marple_tcp_nmo']} #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'marple_tcp_nmo_table':1} #key: table name, val: table size

        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'marple_tcp_nmo_table': {'marple_tcp_nmo':['ALU1','ALU2','ALU3']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'marple_tcp_nmo_table': {'marple_tcp_nmo': [['ALU1','ALU2'], ['ALU2','ALU3']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        } #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU2'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU1'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU2']],
                        's1':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        
        match_dep = [['ingress_port_properties', 'marple_tcp_nmo_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 10:
        # benchmark 2 opt:0m0.781s, feasible:0m0.501s
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16','pkt_17','pkt_18','pkt_19','pkt_20','pkt_21','pkt_22','pkt_23','pkt_24','pkt_25','pkt_26','pkt_27','pkt_28','pkt_29','pkt_30','pkt_31','pkt_32','pkt_33','pkt_34']
        tmp_fields_def = ['tmp_0']
        stateful_var_def = ['s0', 's1']

        table_act_dic = {'fabric_ingress_dst_lkp':['switch_fabric_unicast_packet','terminate_fabric_unicast_packet','switch_fabric_multicast_packet','terminate_fabric_multicast_packet','terminate_cpu_packet'],
                        'storm_control':['set_storm_control_meter'],
                        'marple_tcp_nmo_table':['marple_tcp_nmo']}
        table_size_dic = {'fabric_ingress_dst_lkp':1,
                            'storm_control':512,
                            'marple_tcp_nmo_table':1}

        action_alu_dic = {'fabric_ingress_dst_lkp': {'terminate_cpu_packet':['ALU1','ALU2','ALU3','ALU4'], 
                                                    'switch_fabric_unicast_packet':['ALU1','ALU2','ALU3'], 
                                                    'terminate_fabric_unicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7'],
                                                    'switch_fabric_multicast_packet':['ALU1','ALU2'], 
                                                    'terminate_fabric_multicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'storm_control': {'set_storm_control_meter':['ALU1']},
                            'marple_tcp_nmo_table': {'marple_tcp_nmo':['ALU1','ALU2','ALU3']}
                            }
        alu_dep_dic = {'marple_tcp_nmo_table': {'marple_tcp_nmo': [['ALU1','ALU2'], ['ALU2','ALU3']]}}

        pkt_alu_dic = {
            'pkt_0':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU1'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU1']],
            'pkt_2':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU2']],
            'pkt_4':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU3'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU6']],
            'pkt_6':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU7'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU7']],
            'pkt_8':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU1'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU1']],
            'pkt_9':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU2']],
            'pkt_11':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU3']],
            'pkt_14':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU1']],
            'pkt_16':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU3'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU2']],
            'pkt_18':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU3']],
            'pkt_20':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU5'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU4']],
            'pkt_22':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU6'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU5']],
            'pkt_32':[['storm_control','set_storm_control_meter','ALU1']],
        }
        tmp_alu_dic = {'tmp_0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU2'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU1'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU2']],
                        's1':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['fabric_ingress_dst_lkp', 'marple_tcp_nmo_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 11:
        # benchmark 3 0m1.137s 0m0.639s
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11']
        tmp_fields_def = ['tmp_0']
        stateful_var_def = ['s0', 's1']

        table_act_dic = {'ipv6_multicast_route_star_g':['multicast_route_star_g_miss_1','multicast_route_sm_star_g_hit_1','multicast_route_bidir_star_g_hit_1'],
                        'bd_flood':['set_bd_flood_mc_index'],
                        'marple_tcp_nmo_table':['marple_tcp_nmo']}
        table_size_dic = {'ipv6_multicast_route_star_g':1024,
                            'bd_flood':1024,
                            'marple_tcp_nmo_table':1}
        action_alu_dic = {
            'ipv6_multicast_route_star_g':{'multicast_route_star_g_miss_1':['ALU1'],
            'multicast_route_sm_star_g_hit_1':['ALU1','ALU2','ALU3','ALU4'],
            'multicast_route_bidir_star_g_hit_1':['ALU1','ALU2','ALU3','ALU4']},
            'bd_flood':{'set_bd_flood_mc_index':['ALU1']},
            'marple_tcp_nmo_table': {'marple_tcp_nmo':['ALU1','ALU2','ALU3']}
        }
        alu_dep_dic = {'marple_tcp_nmo_table': {'marple_tcp_nmo': [['ALU1','ALU2'], ['ALU2','ALU3']]}}

        pkt_alu_dic = {
            'pkt_0':[['ipv6_multicast_route_star_g','multicast_route_star_g_miss_1','ALU1']],
            'pkt_1':[['ipv6_multicast_route_star_g','multicast_route_sm_star_g_hit_1','ALU1'],['ipv6_multicast_route_star_g','multicast_route_bidir_star_g_hit_1','ALU1']],
            'pkt_2':[['ipv6_multicast_route_star_g','multicast_route_sm_star_g_hit_1','ALU2'],['ipv6_multicast_route_star_g','multicast_route_bidir_star_g_hit_1','ALU2']],
            'pkt_3':[['ipv6_multicast_route_star_g','multicast_route_sm_star_g_hit_1','ALU3'],['ipv6_multicast_route_star_g','multicast_route_bidir_star_g_hit_1','ALU3']],
            'pkt_4':[['ipv6_multicast_route_star_g','multicast_route_sm_star_g_hit_1','ALU4'],['ipv6_multicast_route_star_g','multicast_route_bidir_star_g_hit_1','ALU4']],
            'pkt_9':[['bd_flood','set_bd_flood_mc_index','ALU1']],
        }
        tmp_alu_dic = {'tmp_0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU2'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU1'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU2']],
                        's1':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['ipv6_multicast_route_star_g', 'marple_tcp_nmo_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 12:
        # benchmark 4 0m0.967s 0m0.502s
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9']
        tmp_fields_def = ['tmp_0']
        stateful_var_def = ['s0', 's1']
        table_act_dic = {'ipv4_dest_vtep':['set_tunnel_termination_flag','set_tunnel_vni_and_termination_flag'],
                        'ipv4_urpf':['ipv4_urpf_hit'],
                        'marple_tcp_nmo_table':['marple_tcp_nmo']}
        table_size_dic = {'ipv4_dest_vtep':1024,
                            'ipv4_urpf':1024,
                            'marple_tcp_nmo_table':1}
        action_alu_dic = {
            'ipv4_dest_vtep':{'set_tunnel_termination_flag':['ALU1'],
            'set_tunnel_vni_and_termination_flag':['ALU1','ALU2']},
            'ipv4_urpf':{'ipv4_urpf_hit':['ALU1','ALU2','ALU3']},
            'marple_tcp_nmo_table': {'marple_tcp_nmo':['ALU1','ALU2','ALU3']}
        }
        alu_dep_dic = {'marple_tcp_nmo_table': {'marple_tcp_nmo': [['ALU1','ALU2'], ['ALU2','ALU3']]}}
        pkt_alu_dic = {
            'pkt_0':[['ipv4_dest_vtep','set_tunnel_termination_flag','ALU1'],['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU2']],
            'pkt_1':[['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU1']],
            'pkt_5':[['ipv4_urpf','ipv4_urpf_hit','ALU1']],
            'pkt_6':[['ipv4_urpf','ipv4_urpf_hit','ALU2']],
            'pkt_7':[['ipv4_urpf','ipv4_urpf_hit','ALU3']]
        }
        tmp_alu_dic = {'tmp_0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU2'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU1'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU2']],
                        's1':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['ipv4_dest_vtep', 'marple_tcp_nmo_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 13:
        # benchmark 11 
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'rcp_table':['rcp']} #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'rcp_table':1} #key: table name, val: table size

        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'rcp_table': {'rcp':['ALU1','ALU2','ALU3','ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'rcp_table': {'rcp': [['ALU2','ALU3'], ['ALU2','ALU4']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        } #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {'tmp_0':[['rcp_table','rcp','ALU2'],['rcp_table','rcp','ALU3'],['rcp_table','rcp','ALU4']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['rcp_table','rcp','ALU1']],
                        's1':[['rcp_table','rcp','ALU3']],
                        's2':[['rcp_table','rcp','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        
        match_dep = [['ingress_port_properties', 'rcp_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    # benchmark 12 
    elif candidate == 14:
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16','pkt_17','pkt_18','pkt_19','pkt_20','pkt_21','pkt_22','pkt_23','pkt_24','pkt_25','pkt_26','pkt_27','pkt_28','pkt_29','pkt_30','pkt_31','pkt_32','pkt_33','pkt_34']
        tmp_fields_def = ['tmp_0'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2'] # all stateful variables

        table_act_dic = {'fabric_ingress_dst_lkp':['switch_fabric_unicast_packet','terminate_fabric_unicast_packet','switch_fabric_multicast_packet','terminate_fabric_multicast_packet','terminate_cpu_packet'],
                        'storm_control':['set_storm_control_meter'],
                        'rcp_table':['rcp']}
        table_size_dic = {'fabric_ingress_dst_lkp':1,
                            'storm_control':512,
                            'rcp_table':1}

        action_alu_dic = {'fabric_ingress_dst_lkp': {'terminate_cpu_packet':['ALU1','ALU2','ALU3','ALU4'], 
                                                    'switch_fabric_unicast_packet':['ALU1','ALU2','ALU3'], 
                                                    'terminate_fabric_unicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7'],
                                                    'switch_fabric_multicast_packet':['ALU1','ALU2'], 
                                                    'terminate_fabric_multicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'storm_control': {'set_storm_control_meter':['ALU1']},
                            'rcp_table': {'rcp':['ALU1','ALU2','ALU3','ALU4']}
                            }
        alu_dep_dic = {'rcp_table': {'rcp': [['ALU2','ALU3'], ['ALU2','ALU4']]}}

        pkt_alu_dic = {
            'pkt_0':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU1'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU1']],
            'pkt_2':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU2']],
            'pkt_4':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU3'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU6']],
            'pkt_6':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU7'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU7']],
            'pkt_8':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU1'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU1']],
            'pkt_9':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU2']],
            'pkt_11':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU3']],
            'pkt_14':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU1']],
            'pkt_16':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU3'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU2']],
            'pkt_18':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU3']],
            'pkt_20':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU5'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU4']],
            'pkt_22':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU6'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU5']],
            'pkt_32':[['storm_control','set_storm_control_meter','ALU1']],
        }
        tmp_alu_dic = {'tmp_0':[['rcp_table','rcp','ALU2'],['rcp_table','rcp','ALU3'],['rcp_table','rcp','ALU4']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['rcp_table','rcp','ALU1']],
                        's1':[['rcp_table','rcp','ALU3']],
                        's2':[['rcp_table','rcp','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['fabric_ingress_dst_lkp', 'rcp_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 15:
        # benchmark 21 
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0','tmp_1'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2', 's3', 's4'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'marple_tcp_nmo_table': ['marple_tcp_nmo'],
                        'rcp_table':['rcp']} #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'marple_tcp_nmo_table':1,
                            'rcp_table':1} #key: table name, val: table size

        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'marple_tcp_nmo_table': {'marple_tcp_nmo':['ALU1','ALU2','ALU3']},
                            'rcp_table': {'rcp':['ALU1','ALU2','ALU3','ALU4']}} #key: table name, val: dictionary whose key is action name and whose value is list of alus
        
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'marple_tcp_nmo_table': {'marple_tcp_nmo': [['ALU1','ALU2'], ['ALU2','ALU3']]},
                        'rcp_table': {'rcp': [['ALU2','ALU3'], ['ALU2','ALU4']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        } #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {
            'tmp_0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU2'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']],
            'tmp_1':[['rcp_table','rcp','ALU2'],['rcp_table','rcp','ALU3'],['rcp_table','rcp','ALU4']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU1'],['marple_tcp_nmo_table','marple_tcp_nmo','ALU2']],
                        's1':[['marple_tcp_nmo_table','marple_tcp_nmo','ALU3']],
                        's2':[['rcp_table','rcp','ALU1']],
                        's3':[['rcp_table','rcp','ALU3']],
                        's4':[['rcp_table','rcp','ALU4']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        
        match_dep = [['ingress_port_properties', 'rcp_table'],['ingress_port_properties','marple_tcp_nmo_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = [] 
    elif candidate == 16:
        # benchmark 31 
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0','tmp_1'] # all temporary variables
        stateful_var_def = ['s0', 's1', 's2'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'learn_filter_table': ['learn_filter']
                        } #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'learn_filter_table':1} #key: table name, val: table size
        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'learn_filter_table': {'learn_filter':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        
        #key: table name, val: dictionary whose key is action name and whose value is list of pairs showing dependency among alus
        alu_dep_dic = {'learn_filter_table': {'learn_filter': [['ALU1','ALU4'], ['ALU2','ALU4'],
                                                                ['ALU3','ALU5'], ['ALU4','ALU6'], ['ALU5','ALU6']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        } #key: packet field in def, val: a list of list of size 3, [['table name', 'action name', 'alu name']], the corresponding alu modifies the key field
        tmp_alu_dic = {
            'tmp_0':[['learn_filter_table','learn_filter','ALU4'],['learn_filter_table','learn_filter','ALU6']],
            'tmp_1':[['learn_filter_table','learn_filter','ALU5'],['learn_filter_table','learn_filter','ALU6']]
                        } #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['learn_filter_table','learn_filter','ALU1'],['learn_filter_table','learn_filter','ALU4']],
                        's1':[['learn_filter_table','learn_filter','ALU2'],['learn_filter_table','learn_filter','ALU4']],
                        's2':[['learn_filter_table','learn_filter','ALU3'],['learn_filter_table','learn_filter','ALU5']],
                        } #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['ingress_port_properties', 'learn_filter_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 17:
        # benchmark 41 
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'sampling_table': ['sampling']
                        } #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'sampling_table':1} #key: table name, val: table size
        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'sampling_table': {'sampling':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'sampling_table': {'sampling': [['ALU1','ALU2']]}}

        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2'],['sampling_table','sampling','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        }
        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['sampling_table','sampling','ALU1'],['sampling_table','sampling','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        match_dep = [['ingress_port_properties', 'sampling_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 18:
        # benchmark 51 
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'marple_new_flow_table': ['marple_new_flow']
                        } #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'marple_new_flow_table':1} #key: table name, val: table size
        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'marple_new_flow_table': {'marple_new_flow':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'marple_new_flow_table': {'marple_new_flow': [['ALU1','ALU2']]}}

        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2'],['marple_new_flow_table','marple_new_flow','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        }
        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['marple_new_flow_table','marple_new_flow','ALU1'],['marple_new_flow_table','marple_new_flow','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        match_dep = [['ingress_port_properties', 'marple_new_flow_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 19:
        # benchmark 61
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0','tmp_1'] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'flowlets_table': ['flowlets']
                        } #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'flowlets_table':1} #key: table name, val: table size
        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'flowlets_table': {'flowlets':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'flowlets_table': {'flowlets': [['ALU4','ALU1'],['ALU2','ALU4'],['ALU3','ALU4']]}}

        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4'],['flowlets_table','flowlets','ALU1']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        }
        tmp_alu_dic = {'tmp_0':[['flowlets_table','flowlets','ALU3'],['flowlets_table','flowlets','ALU4']],
                        'tmp_1':[['flowlets_table','flowlets','ALU4'],['flowlets_table','flowlets','ALU1']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['flowlets_table','flowlets','ALU2'],['flowlets_table','flowlets','ALU4']],
                        's1':[['flowlets_table','flowlets','ALU1']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        match_dep = [['ingress_port_properties', 'flowlets_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 20:
        # benchmark 71
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = ['tmp_0','tmp_1','tmp_2','tmp_3','tmp_4'] # all temporary variables
        stateful_var_def = ['s0','s1'] # all stateful variables

        table_act_dic = {'validate_outer_ipv4_packet':['set_valid_outer_ipv4_packet', 'set_malformed_outer_ipv4_packet'],
                        'ingress_port_properties':['set_ingress_port_properties'],
                        'blue_increase_table': ['blue_increase']
                        } #key: table name, val: list of actions
        table_size_dic = {'ingress_port_properties':288, 
                            'validate_outer_ipv4_packet':512,
                            'blue_increase_table':1} #key: table name, val: table size
        action_alu_dic = {'ingress_port_properties': {'set_ingress_port_properties' : ['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'validate_outer_ipv4_packet': {'set_valid_outer_ipv4_packet':['ALU1','ALU2','ALU3'], 'set_malformed_outer_ipv4_packet':['ALU1','ALU2']},
                            'blue_increase_table': {'blue_increase':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7','ALU8']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'blue_increase_table': {'blue_increase': [['ALU4','ALU7'],['ALU2','ALU8'],['ALU3','ALU2'],
                                                                ['ALU5','ALU7'],['ALU6','ALU7'],['ALU7','ALU8'],['ALU8','ALU1']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_port_properties','set_ingress_port_properties','ALU1']],
            'pkt_1':[['ingress_port_properties','set_ingress_port_properties','ALU2']],
            'pkt_2':[['ingress_port_properties','set_ingress_port_properties','ALU3']],
            'pkt_3':[['ingress_port_properties','set_ingress_port_properties','ALU4'],['flowlets_table','flowlets','ALU1']],
            'pkt_4':[['ingress_port_properties','set_ingress_port_properties','ALU5']],
            'pkt_5':[['ingress_port_properties','set_ingress_port_properties','ALU6']],
            'pkt_6':[['ingress_port_properties','set_ingress_port_properties','ALU7']],
            'pkt_8':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU1']],
            'pkt_9':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU2']],
            'pkt_11':[['validate_outer_ipv4_packet','set_valid_outer_ipv4_packet','ALU3']],
            'pkt_13':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU1']],
            'pkt_14':[['validate_outer_ipv4_packet','set_malformed_outer_ipv4_packet','ALU2']]
        }
        tmp_alu_dic = {'tmp_0':[['blue_increase_table','blue_increase','ALU4'],['blue_increase_table','blue_increase','ALU7']],
                        'tmp_1':[['blue_increase_table','blue_increase','ALU5'],['blue_increase_table','blue_increase','ALU7']],
                        'tmp_2':[['blue_increase_table','blue_increase','ALU6'],['blue_increase_table','blue_increase','ALU7']],
                        'tmp_3':[['blue_increase_table','blue_increase','ALU7'],['blue_increase_table','blue_increase','ALU8']],
                        'tmp_4':[['blue_increase_table','blue_increase','ALU8'],['blue_increase_table','blue_increase','ALU1']]} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['blue_increase_table','blue_increase','ALU2'],['blue_increase_table','blue_increase','ALU8']],
                        's1':[['blue_increase_table','blue_increase','ALU1']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['ingress_port_properties', 'blue_increase_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 21:
        # benchmark 42
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16','pkt_17','pkt_18','pkt_19','pkt_20','pkt_21','pkt_22','pkt_23','pkt_24','pkt_25','pkt_26','pkt_27','pkt_28','pkt_29','pkt_30','pkt_31','pkt_32','pkt_33','pkt_34']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'fabric_ingress_dst_lkp':['switch_fabric_unicast_packet','terminate_fabric_unicast_packet','switch_fabric_multicast_packet','terminate_fabric_multicast_packet','terminate_cpu_packet'],
                        'storm_control':['set_storm_control_meter'],
                        'sampling_table': ['sampling']}
        table_size_dic = {'fabric_ingress_dst_lkp':1,
                            'storm_control':512,
                            'sampling_table':1}

        action_alu_dic = {'fabric_ingress_dst_lkp': {'terminate_cpu_packet':['ALU1','ALU2','ALU3','ALU4'], 
                                                    'switch_fabric_unicast_packet':['ALU1','ALU2','ALU3'], 
                                                    'terminate_fabric_unicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7'],
                                                    'switch_fabric_multicast_packet':['ALU1','ALU2'], 
                                                    'terminate_fabric_multicast_packet':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7']},
                            'storm_control': {'set_storm_control_meter':['ALU1']},
                            'sampling_table': {'sampling':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'sampling_table': {'sampling': [['ALU1','ALU2']]}}

        pkt_alu_dic = {
            'pkt_0':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU1'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU1']],
            'pkt_2':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU2']],
            'pkt_4':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU3'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU6']],
            'pkt_6':[['fabric_ingress_dst_lkp','terminate_cpu_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU7'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU7']],
            'pkt_8':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU1'],['fabric_ingress_dst_lkp','switch_fabric_multicast_packet','ALU1']],
            'pkt_9':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU2']],
            'pkt_11':[['fabric_ingress_dst_lkp','switch_fabric_unicast_packet','ALU3']],
            'pkt_14':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU2'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU1']],
            'pkt_16':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU3'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU2']],
            'pkt_18':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU4'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU3']],
            'pkt_20':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU5'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU4']],
            'pkt_22':[['fabric_ingress_dst_lkp','terminate_fabric_unicast_packet','ALU6'],['fabric_ingress_dst_lkp','terminate_fabric_multicast_packet','ALU5']],
            'pkt_32':[['storm_control','set_storm_control_meter','ALU1']],
        }
        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['sampling_table','sampling','ALU1'],['sampling_table','sampling','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var
        match_dep = [['fabric_ingress_dst_lkp', 'sampling_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 22:
        # three table benchmark 1
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16','pkt_17','pkt_18','pkt_19','pkt_20']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'ingress_qos_map_pcp':['set_ingress_tc','set_ingress_color','set_ingress_tc_and_color'],
                        'outer_ipv6_multicast_star_g':['outer_multicast_route_sm_star_g_hit','outer_multicast_route_bidir_star_g_hit','outer_multicast_bridge_star_g_hit'],
                        'ipv6_urpf':['ipv6_urpf_hit'],
                        'sampling_table': ['sampling']}
        table_size_dic = {'ingress_qos_map_pcp':64,
                            'outer_ipv6_multicast_star_g':512,
                            'ipv6_urpf':1024,
                            'sampling_table':1}

        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['sampling_table','sampling','ALU1'],['sampling_table','sampling','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        action_alu_dic = {'ingress_qos_map_pcp': {'set_ingress_tc':['ALU1'], 
                                                    'set_ingress_color':['ALU1'], 
                                                    'set_ingress_tc_and_color':['ALU1','ALU2'],
                                                    },
                            'outer_ipv6_multicast_star_g': {'outer_multicast_route_sm_star_g_hit':['ALU1','ALU2','ALU3','ALU4','ALU5'],
                            'outer_multicast_route_bidir_star_g_hit':['ALU1','ALU2','ALU3','ALU4','ALU5'],
                            'outer_multicast_bridge_star_g_hit':['ALU1','ALU2','ALU3']},
                            'ipv6_urpf':{'ipv6_urpf_hit':['ALU1','ALU2','ALU3']},
                            'sampling_table': {'sampling':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'sampling_table': {'sampling': [['ALU1','ALU2']]}}

        pkt_alu_dic = {
            'pkt_0':[['ingress_qos_map_pcp','set_ingress_tc','ALU1'],['ingress_qos_map_pcp','set_ingress_tc_and_color','ALU1']],
            'pkt_1':[['ingress_qos_map_pcp','set_ingress_color','ALU1'],['ingress_qos_map_pcp','set_ingress_tc_and_color','ALU2']],
            'pkt_4':[['outer_ipv6_multicast_star_g','outer_multicast_route_sm_star_g_hit','ALU1'],['outer_ipv6_multicast_star_g','outer_multicast_route_bidir_star_g_hit','ALU1']],
            'pkt_5':[['outer_ipv6_multicast_star_g','outer_multicast_route_sm_star_g_hit','ALU2'],['outer_ipv6_multicast_star_g','outer_multicast_route_bidir_star_g_hit','ALU2'],['outer_ipv6_multicast_star_g','outer_multicast_bridge_star_g_hit','ALU1']],
            'pkt_6':[['outer_ipv6_multicast_star_g','outer_multicast_route_sm_star_g_hit','ALU3'],['outer_ipv6_multicast_star_g','outer_multicast_route_bidir_star_g_hit','ALU3']],
            'pkt_7':[['outer_ipv6_multicast_star_g','outer_multicast_route_sm_star_g_hit','ALU4'],['outer_ipv6_multicast_star_g','outer_multicast_route_bidir_star_g_hit','ALU4']],
            'pkt_9':[['outer_ipv6_multicast_star_g','outer_multicast_route_sm_star_g_hit','ALU5'],['outer_ipv6_multicast_star_g','outer_multicast_route_bidir_star_g_hit','ALU5'],['outer_ipv6_multicast_star_g','outer_multicast_bridge_star_g_hit','ALU3']],
            'pkt_11':[['outer_ipv6_multicast_star_g','outer_multicast_bridge_star_g_hit','ALU2']],
            'pkt_15':[['ipv6_urpf','ipv6_urpf_hit','ALU1']],
            'pkt_16':[['ipv6_urpf','ipv6_urpf_hit','ALU2']],
            'pkt_17':[['ipv6_urpf','ipv6_urpf_hit','ALU3']],
        }

        match_dep = [['ingress_qos_map_pcp', 'sampling_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 23:
        # three table benchmark 4
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16','pkt_17','pkt_18','pkt_19','pkt_20']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'ingress_l4_src_port':['set_ingress_src_port_range_id'],
                        'smac':['smac_miss','smac_hit'],
                        'ipv6_racl':['racl_deny','racl_permit','racl_redirect_nexthop','racl_redirect_ecmp'],
                        'sampling_table': ['sampling']}
        table_size_dic = {'ingress_l4_src_port':512,
                            'smac':1024,
                            'ipv6_racl':512,
                            'sampling_table':1}

        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['sampling_table','sampling','ALU1'],['sampling_table','sampling','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        action_alu_dic = {'ingress_l4_src_port': {'set_ingress_src_port_range_id':['ALU1']
                                                    },
                            'smac': {'smac_miss':['ALU1'],'smac_hit':['ALU1']},
                            'ipv6_racl':{'racl_deny':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6'],
                                        'racl_permit':['ALU1','ALU2','ALU3','ALU4','ALU5'],
                                        'racl_redirect_nexthop':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7','ALU8'],
                                        'racl_redirect_ecmp':['ALU1','ALU2','ALU3','ALU4','ALU5','ALU6','ALU7','ALU8']},
                            'sampling_table': {'sampling':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'sampling_table': {'sampling': [['ALU1','ALU2']]}}
        pkt_alu_dic = {
            'pkt_0':[['ingress_l4_src_port','set_ingress_src_port_range_id','ALU1']],
            'pkt_1':[['sampling_table','sampling','ALU2']],
            'pkt_2':[['smac','smac_miss','ALU1']],
            'pkt_3':[['smac','smac_hit','ALU1']],
            'pkt_7':[['ipv6_racl','racl_deny','ALU1']],
            'pkt_8':[['ipv6_racl','racl_deny','ALU2'],['ipv6_racl','racl_permit','ALU1'],['ipv6_racl','racl_redirect_nexthop','ALU4'],['ipv6_racl','racl_redirect_ecmp','ALU4']],
            'pkt_9':[['ipv6_racl','racl_deny','ALU3'],['ipv6_racl','racl_permit','ALU2'],['ipv6_racl','racl_redirect_nexthop','ALU5'],['ipv6_racl','racl_redirect_ecmp','ALU5']],
            'pkt_10':[['ipv6_racl','racl_deny','ALU4'],['ipv6_racl','racl_permit','ALU3'],['ipv6_racl','racl_redirect_nexthop','ALU6'],['ipv6_racl','racl_redirect_ecmp','ALU6']],
            'pkt_11':[['ipv6_racl','racl_deny','ALU5'],['ipv6_racl','racl_permit','ALU4'],['ipv6_racl','racl_redirect_nexthop','ALU7'],['ipv6_racl','racl_redirect_ecmp','ALU7']],
            'pkt_12':[['ipv6_racl','racl_deny','ALU6'],['ipv6_racl','racl_permit','ALU5'],['ipv6_racl','racl_redirect_nexthop','ALU8'],['ipv6_racl','racl_redirect_ecmp','ALU8']],
            'pkt_13':[['ipv6_racl','racl_redirect_nexthop','ALU1'],['ipv6_racl','racl_redirect_ecmp','ALU1']],
            'pkt_14':[['ipv6_racl','racl_redirect_nexthop','ALU2'],['ipv6_racl','racl_redirect_ecmp','ALU2']],
            'pkt_15':[['ipv6_racl','racl_redirect_nexthop','ALU3'],['ipv6_racl','racl_redirect_ecmp','ALU3']]
        }

        match_dep = [['ingress_l4_src_port', 'ipv6_racl'],['ingress_l4_src_port','sampling_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []
    elif candidate == 24:
        # four table benchmark 5
        pkt_fields_def = ['pkt_0','pkt_1','pkt_2','pkt_3','pkt_4','pkt_5','pkt_6','pkt_7','pkt_8','pkt_9','pkt_10','pkt_11','pkt_12','pkt_13','pkt_14','pkt_15','pkt_16']
        tmp_fields_def = [] # all temporary variables
        stateful_var_def = ['s0'] # all stateful variables

        table_act_dic = {'ipv4_dest_vtep':['set_tunnel_termination_flag','set_tunnel_vni_and_termination_flag'],
                        'ingress_l4_src_port':['set_ingress_src_port_range_id'],
                        'ipv4_multicast_bridge':['multicast_bridge_s_g_hit'],
                        'ipv4_multicast_route':['multicast_route_s_g_hit_0'],
                        'sampling_table': ['sampling']}
        table_size_dic = {'ipv4_dest_vtep':1024,
                            'ingress_l4_src_port':512,
                            'ipv4_multicast_bridge':1024,
                            'ipv4_multicast_route':1024,
                            'sampling_table':1}

        tmp_alu_dic = {} #key: tmp packet fields, val: a list of list of size 3, [['table name', 'action name', 'alu name']]
        state_alu_dic = {'s0':[['sampling_table','sampling','ALU1'],['sampling_table','sampling','ALU2']]} #key: packet field in def, val: a list of size 3, ['table name', 'action name', 'alu name'], the corresponding alu modifies the key stateful var

        action_alu_dic = {'ipv4_dest_vtep': {'set_tunnel_termination_flag':['ALU1'],
                                            'set_tunnel_vni_and_termination_flag':['ALU1','ALU2']},
                            'ingress_l4_src_port': {'set_ingress_src_port_range_id':['ALU1']},
                            'ipv4_multicast_bridge':{'multicast_bridge_s_g_hit':['ALU1','ALU2']},
                            'ipv4_multicast_route':{'multicast_route_s_g_hit_0':['ALU1','ALU2','ALU3','ALU4']}, 
                            'sampling_table': {'sampling':['ALU1','ALU2']}
                            } #key: table name, val: dictionary whose key is action name and whose value is list of alus
        alu_dep_dic = {'sampling_table': {'sampling': [['ALU1','ALU2']]}}

        pkt_alu_dic = {
            'pkt_0':[['ipv4_dest_vtep','set_tunnel_termination_flag','ALU1'],['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU2']],
            'pkt_1':[['ipv4_dest_vtep','set_tunnel_vni_and_termination_flag','ALU1'],['sampling_table','sampling','ALU2']],
            'pkt_5':[['ingress_l4_src_port','set_ingress_src_port_range_id','ALU1']],
            'pkt_7':[['ipv4_multicast_bridge','multicast_bridge_s_g_hit','ALU1']],
            'pkt_8':[['ipv4_multicast_bridge','multicast_bridge_s_g_hit','ALU2']],
            'pkt_12':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU1']],
            'pkt_13':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU2']],
            'pkt_14':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU3']],
            'pkt_15':[['ipv4_multicast_route','multicast_route_s_g_hit_0','ALU4']]
        }

        match_dep = [['ipv4_dest_vtep', 'sampling_table']] #list of list, for each pari [T1, T2], T2 has match dependency on T1
        action_dep = [] #list of list, for each pari [T1, T2], T2 has action dependency on T1
        reverse_dep = [] #list of list, for each pari [T1, T2], T2 has reverse dependency on T1
        successor_dep = []

    # if len(sys.argv) != 2:
    #     print("Usage:", sys.argv[0], "<mode (either Optimal or Feasible)> <candidate number (1-24)>")
    #     exit(1)
    # else:
    #     mode = sys.argv[1]
    #     assert mode == "Optimal" or mode == "Feasible", "the mode should be either Optimal or Feasible"
    # if mode == "Optimal":
    #     opt = True
    # else:
    #     opt = False
    solve_ILP(pkt_fields_def, tmp_fields_def, stateful_var_def, 
    table_act_dic, table_size_dic, action_alu_dic, alu_dep_dic,
    pkt_alu_dic, tmp_alu_dic, state_alu_dic,
    match_dep, action_dep, successor_dep, reverse_dep, opt)

    # TODO: List all info needed for txt gen
    table_match_dic = {} #key: table name, val: list of packet fields for match
    table_match_val_dic = {} #key: table name, val: list of match value
    alu_content_dic = {} #key: alu name, val: content of this alu



if __name__ == '__main__':
    main(sys.argv)
