echo "Z3 Optimal mode"
for ((i=1;i<25;i++)); do
    echo "benchmark $i"
    time python3 ILP_z3.py Optimal $i | grep stages
done
echo "-----------------------"
echo "Z3 Satisfiable mode"
for ((i=1;i<25;i++)); do
    echo "benchmark $i"
    time python3 ILP_z3.py Feasible $i | grep stages
done
echo "-----------------------"
echo "Gurobi Optimal mode"
for ((i=1;i<25;i++)); do
    echo "benchmark $i"
    time python3 ILP_Gurobi.py Optimal $i | grep stages
done
echo "-----------------------"
echo "Gurobi Satisfiable mode"
for ((i=1;i<25;i++)); do
    echo "benchmark $i"
    time python3 ILP_Gurobi.py Feasible $i | grep stages
done