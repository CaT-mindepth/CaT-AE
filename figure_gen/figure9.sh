echo "Optimal mode"
for ((i=1;i<40;i++)); do
    echo "number of stages is $i"
    (time python3 Gurobi_opt_vs_fea.py 256 16 $i Optimal >/dev/null;) |& grep real
done
echo "Feasible mode"
for ((i=1;i<40;i++)); do
    echo "number of stages is $i"
    (time python3 Gurobi_opt_vs_fea.py 256 16 $i Feasible >/dev/null;) |& grep real
done
