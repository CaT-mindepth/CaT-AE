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
        m.addConstr(cost >= beg_var)
        m.addConstr(cost >= end_var - 1)
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
        m.addConstr(cost >= beg_var)
        m.addConstr(cost >= end_var - 1)


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
            m.addConstr(cost >= beg_var)
            m.addConstr(cost >= end_var - 1)

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
        # for v in m.getVars():
        #     # if v.varName != 'cost' and v.varName.find('stage') == -1:
        #     if v.varName in var_l or v.varName == 'cost':
        #         print('%s %g' % (v.varName, v.x))
        #     if v.varName == 'cost':
        #         print('Total number of stages used is %g (zero index)' % v.x)
        # print("************************************************")
        # print(m.getJSONSolution())
        return m.getJSONSolution()        
    else:
        print("Sad")
