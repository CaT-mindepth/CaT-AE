echo "Optimal mode"
for ((i=1;i<31;i++)); do
    echo "number of tables per stage is $i"
    (time python3 Gurobi_opt_vs_fea.py 256 $i 12 Optimal >/dev/null;) |& grep real
done
echo "Feasible mode"
for ((i=1;i<31;i++)); do
    echo "number of tables per stage is $i"
    (time python3 Gurobi_opt_vs_fea.py 256 $i 12 Feasible >/dev/null;) |& grep real
done
