import sys

from z3 import *
import math

num_of_entries_per_table = 256
num_of_alus_per_stage = 64
num_of_table_per_stage = 8
num_of_stages = 12

# TODO: replace binary ints by bool variables and use cardinality constraints instead of sum
# TODO: collect math.ceil(float(table_size_dic[t]) / num_of_entries_per_table) into a dictionary

def compare_func(ele):
    return str(ele)

def gen_and_solve_ILP(pkt_fields_def, tmp_fields_def, stateful_var_def,
                        table_act_dic, table_size_dic, action_alu_dic,
                        alu_dep_dic, 
                        pkt_alu_dic, tmp_alu_dic, state_alu_dic,
                        match_dep, action_dep, successor_dep, reverse_dep,
                        optimization):
    # Get the place where we need to newly allocate the alus
    used_alu = len(pkt_fields_def)
    
    z3_match_list = [Int('%s_M%s' % (t, i)) for t in table_size_dic for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table))]
    z3_alu_list = [Int('%s_M%s_%s_%s' % (t, i, action, alu)) for t in table_size_dic for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table))
    for action in table_act_dic[t] for alu in action_alu_dic[t][action]]
    # print(z3_match_list)
    # print(z3_alu_list)
    
    z3_table_loc_vec = []
    for j in range(num_of_stages):
        curr_list = []
        for t in table_size_dic:
            for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
                curr_list.append(Int('%s_M%s_stage%s' % (t, i, j)))
        z3_table_loc_vec.append(curr_list)
    # print(z3_table_loc_vec)
    
    z3_alu_loc_vec = []
    for t in table_size_dic:
        for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
            for action in table_act_dic[t]:
                for alu in action_alu_dic[t][action]:
                    curr_list = []
                    for j in range(num_of_stages):
                        curr_list.append(Int('%s_M%s_%s_%s_stage%s' % (t, i, action, alu, j)))
                    z3_alu_loc_vec.append(curr_list)
    # print(z3_alu_loc_vec)
    
    # Constraint 0: all binary variable should be either 0 or 1
    binary_c = []
    for mem in z3_table_loc_vec:
        for v in mem:
            binary_c.append(And(v >= 0, v <= 1))
    for mem in z3_alu_loc_vec:
        for v in mem:
            binary_c.append(And(v >= 0, v <= 1))

    # Constraint 1: Match happens before any alus belonging to that table (DONE)
    match_then_action_c = []
    for table in alu_dep_dic:
        for i in range(math.ceil(float(table_size_dic[table]) / num_of_entries_per_table)):
            for action in table_act_dic[table]:
                for alu in action_alu_dic[table][action]:
                    for stage in range(num_of_stages):
                        match_then_action_c.append(Implies(Int('%s_M%s_%s_%s' % (table, i, action, alu)) == stage, Int('%s_M%s' % (table, i)) >= stage))
                        match_then_action_c.append(Implies(Int('%s_M%s_%s_%s' % (table, i, action, alu)) == stage, Int('%s_M%s_stage%s' % (table, i, stage)) == 1))
    # print(match_then_action_c)

    # Constraint 2: All stage numbers cannot be greater than total available stage (DONE)
    match_stage_c = [And(match_s >= 0, match_s < num_of_stages) for match_s in z3_match_list]
    alu_stage_c = [And(alu_s >= 0, alu_s < num_of_stages) for alu_s in z3_alu_list]

    # Constraint 3: alu-level dependency (DONE)
    alu_level_c = []
    for table in alu_dep_dic:
        for i in range(math.ceil(float(table_size_dic[table]) / num_of_entries_per_table)):
            for action in table_act_dic[table]:
                for pair in alu_dep_dic[table][action]:
                    alu1 = pair[0]
                    alu2 = pair[1]
                    alu_level_c.append(Int('%s_M%s_%s_%s' % (table, i, action, alu1)) < Int('%s_M%s_%s_%s' % (table, i, action, alu2)))
    # print(alu_level_c)

    # Constraint 4: No use more tables than available per stage (DONE)
    num_table_c = []
    for i in range(len(z3_table_loc_vec)):
        num_table_c.append(Sum(z3_table_loc_vec[i]) <= num_of_table_per_stage)
        for j in range(len(z3_table_loc_vec[i])):
            num_table_c.append(And(z3_table_loc_vec[i][j] >= 0, z3_table_loc_vec[i][j] <= 1))

    # Constraint 5: An ALU must be allocated to one and exactly one stage (DONE)
    alu_pos_rel_c = []
    for mem in z3_alu_loc_vec:
        alu_pos_rel_c.append(Sum(mem) == 1)
    for t in table_size_dic:
        for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
            for action in table_act_dic[t]:
                for alu in action_alu_dic[t][action]:
                    for j in range(num_of_stages):
                        alu_pos_rel_c.append(Implies(Int('%s_M%s_%s_%s_stage%s' % (t, i, action, alu, j))==1, Int('%s_M%s_%s_%s' % (t, i, action, alu))==j ))
                        alu_pos_rel_c.append(Implies(Int('%s_M%s_%s_%s' % (t, i, action, alu))==j, Int('%s_M%s_%s_%s_stage%s' % (t, i, action, alu, j))==1))
    # print(alu_pos_rel_c)

    cost = Int('cost')
    cost_with_end_c = []
    tmp_state_field_loc_vec = []
    # Create beg and end for tmp and stateful
    for tmp_field in tmp_fields_def:
        tmp_l = []
        for i in range(num_of_stages):
            tmp_l.append(Int('%s_stage%s' % (tmp_field, i)))
        tmp_state_field_loc_vec.append(tmp_l)
        curr_beg = Int('%s_beg' % tmp_field)
        curr_end = Int('%s_end' % tmp_field)
        cost_with_end_c.append(cost >= curr_end - 1)
        alu_pos_rel_c.append(And(curr_beg >= 0, curr_beg < num_of_stages, curr_end >= 0, curr_end < num_of_stages))
        for j in range(len(tmp_alu_dic[tmp_field])):
            mem = tmp_alu_dic[tmp_field][j]
            table = mem[0]
            action = mem[1]
            alu = mem[2]
            if j == 0:
                for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
                    alu_pos_rel_c.append(curr_beg == Int('%s_M%s_%s_%s' % (table, i, action, alu)))
                    alu_pos_rel_c.append(curr_beg + 1 <= curr_end)
            else:
                for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
                    alu_pos_rel_c.append(curr_end >= Int('%s_M%s_%s_%s' % (table, i, action, alu)))

    for tmp_field in tmp_fields_def:
        for i in range(num_of_stages):
            alu_pos_rel_c.append( If(
                And(Int('%s_beg' % tmp_field) <= i, i < Int('%s_end' % tmp_field)), And(Int('%s_stage%s' % (tmp_field, i)) == 1, Int('cost') >= i), Int('%s_stage%s' % (tmp_field, i)) == 0
                ))
    
    for state_var in stateful_var_def:
        tmp_l = []
        for i in range(num_of_stages):
            tmp_l.append(Int('%s_stage%s' % (state_var, i)))
        tmp_state_field_loc_vec.append(tmp_l)
        curr_beg = Int('%s_beg' % state_var)
        curr_end = Int('%s_end' % state_var)
        cost_with_end_c.append(cost >= curr_end - 1)
        alu_pos_rel_c.append(And(curr_beg >= 0, curr_beg < num_of_stages, curr_end >= 0, curr_end < num_of_stages))
        for j in range(len(state_alu_dic[state_var])):
            mem = state_alu_dic[state_var][j]
            table = mem[0]
            action = mem[1]
            alu = mem[2]
            if j == 0:
                for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
                    alu_pos_rel_c.append(curr_beg == Int('%s_M%s_%s_%s' % (table, i, action, alu)))
                    alu_pos_rel_c.append(curr_beg + 1 <= curr_end)
            else:
                for i in range(math.ceil(float(table_size_dic[t]) / num_of_entries_per_table)):
                    alu_pos_rel_c.append(curr_end >= Int('%s_M%s_%s_%s' % (table, i, action, alu)))
    for state_var in stateful_var_def:
        for i in range(num_of_stages):
            alu_pos_rel_c.append( If(
                And(Int('%s_beg' % state_var) <= i, i < Int('%s_end' % state_var)), Int('%s_stage%s' % (state_var, i)) == 1, Int('%s_stage%s' % (state_var, i)) == 0
                ))
    # print("cost_with_end_c =", cost_with_end_c)
    for mem in tmp_state_field_loc_vec:
        for v in mem:
            binary_c.append(And(v >= 0, v <= 1))

    tmp_state_field_loc_vec_transpose = [[tmp_state_field_loc_vec[i][j] for i in range(len(tmp_state_field_loc_vec))] for j in range(len(tmp_state_field_loc_vec[0]))]
    for i in range(len(tmp_state_field_loc_vec_transpose)):
        alu_pos_rel_c.append(Sum(tmp_state_field_loc_vec_transpose[i]) <= (num_of_alus_per_stage - used_alu) )

    # Constraint 6: set a variable cost which is our objective function whose value is >= to any other vars (DONE)
    
    cost_with_match_c = [And(cost >= m_v) for m_v in z3_match_list]
    cost_with_alu_c = [And(cost >= alu_v) for alu_v in z3_alu_list]

    # Constraint 6: table-level constraints for match, action, and reverse dep (DONE)
    table_dep_c = []
    for ele in match_dep:
        t1 = ele[0]
        t2 = ele[1]
        for i in range(math.ceil(float(table_size_dic[t1]) / num_of_entries_per_table)):
            for j in range(math.ceil(float(table_size_dic[t2]) / num_of_entries_per_table)):
                for act1 in table_act_dic[t1]:
                    for act2 in table_act_dic[t2]:
                        for alu1 in action_alu_dic[t1][act1]:
                            for alu2 in action_alu_dic[t2][act2]:
                                table_dep_c.append(And(Int('%s_M%s_%s_%s' % (t1, i, act1, alu1)) < Int('%s_M%s_%s_%s' % (t2, j, act2, alu2))))
    for ele in action_dep:
        t1 = ele[0]
        t2 = ele[1]
        for i in range(math.ceil(float(table_size_dic[t1]) / num_of_entries_per_table)):
            for j in range(math.ceil(float(table_size_dic[t2]) / num_of_entries_per_table)):
                for act1 in table_act_dic[t1]:
                    for act2 in table_act_dic[t2]:
                        for alu1 in action_alu_dic[t1][act1]:
                            for alu2 in action_alu_dic[t2][act2]:
                                table_dep_c.append(And(Int('%s_M%s_%s_%s' % (t1, i, act1, alu1)) < Int('%s_M%s_%s_%s' % (t2, j, act2, alu2))))
    for ele in reverse_dep:
        t1 = ele[0]
        t2 = ele[1]
        for i in range(math.ceil(float(table_size_dic[t1]) / num_of_entries_per_table)):
            for j in range(math.ceil(float(table_size_dic[t2]) / num_of_entries_per_table)):
                for act1 in table_act_dic[t1]:
                    for act2 in table_act_dic[t2]:
                        for alu1 in action_alu_dic[t1][act1]:
                            for alu2 in action_alu_dic[t2][act2]:
                                table_dep_c.append(And(Int('%s_M%s_%s_%s' % (t1, i, act1, alu1)) <= Int('%s_M%s_%s_%s' % (t2, j, act2, alu2))))

    # print("Come here------------------------")
    set_option("parallel.enable", True)
    if optimization:
        opt = Optimize()
        # TODO: add a constraint as soon as we finish building one
        opt.add(binary_c +
            match_then_action_c + 
            match_stage_c + alu_stage_c +
            alu_level_c + 
            num_table_c + 
            alu_pos_rel_c + 
            cost_with_match_c + cost_with_alu_c + cost_with_end_c + 
            table_dep_c)
        opt.minimize(cost)
        print("Solving Optimization problem")
        if opt.check() == sat:
            print("Achieve a solution")
            var_l = []
            for v in opt.model():
                var_l.append(v)
            var_l.sort(key=compare_func)
            # for v in var_l:
            #     if str(v).find('stage') == -1:
            #         print(v, '=' ,opt.model()[v])
        else:
            print("No solution")
        
        # Output the obective function's value Ref:https://www.cs.tau.ac.il/~msagiv/courses/asv/z3py/guide-examples.htm
        print('Objective value is: %s (zero index)' % opt.model()[cost])
        print('Total number of stages is:', int(str(opt.model()[cost])) + 1)
    else:
        print("Solving SAT problem")
        s = Solver()
        s.add(binary_c +
            match_then_action_c + 
            match_stage_c + alu_stage_c +
            alu_level_c + 
            num_table_c + 
            alu_pos_rel_c + 
            cost_with_match_c + cost_with_alu_c + cost_with_end_c + 
            table_dep_c)
        if s.check() == sat:
            print("Achieve a solution")
            var_l = []
            for v in s.model():
                var_l.append(v)
            var_l.sort(key=compare_func)
            # for v in var_l:
            #     if str(v).find('stage') == -1:
            #         print(v, '=', s.model()[v])
            for v in var_l:
                if str(v).find('cost') != -1:
                    print("Objective value is:", s.model()[v], "(zero index)")
        else:
            print("No solution")
    
    # TODO: output the layout of ALU grid

def main(argv):
    """main program."""
    if len(sys.argv) != 3:
        print("Usage:", sys.argv[0], "<mode (either Optimal or Feasible)> <candidate number (1-24)>")
        exit(1)
    else:
        mode = sys.argv[1]
        candidate = int(sys.argv[2])
        assert candidate >= 1 and candidate <= 24, "The candidate number should be between 1 and 24"
        assert mode == "Optimal" or mode == "Feasible", "the mode should be either Optimal or Feasible"
    if mode == "Optimal":
        optimization = True
    else:
        optimization = False
    
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

    gen_and_solve_ILP(pkt_fields_def, tmp_fields_def, stateful_var_def,
                        table_act_dic, table_size_dic, action_alu_dic,
                        alu_dep_dic, 
                        pkt_alu_dic, tmp_alu_dic, state_alu_dic,
                        match_dep, action_dep, successor_dep, reverse_dep,
                        optimization)

if __name__ == "__main__":
        main(sys.argv)
