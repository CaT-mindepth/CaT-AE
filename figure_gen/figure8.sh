echo "Optimal mode"
for ((i=5;i<12;i++)); do
    echo "log number of entries per table is $i"
    (time python3 Gurobi_opt_vs_fea.py $((2**i)) 16 12 Optimal >/dev/null;) |& grep real
done
echo "Feasible mode"
for ((i=5;i<12;i++)); do
    echo "log number of entries per table is $i"
    (time python3 Gurobi_opt_vs_fea.py $((2**i)) 16 12 Feasible >/dev/null;) |& grep real
done