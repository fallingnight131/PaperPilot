#!/bin/bash
cd /Users/fallingnight/代码/Python/2026_3/PaperPilot/backend
eval "$(conda shell.bash hook)"
conda activate PaperPilot
python run.py > server.log 2>&1 &
echo $!
