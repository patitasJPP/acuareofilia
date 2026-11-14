from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SIMULATION=ROOT/'simulacion'
ML=SIMULATION/'ml'
MODELS=SIMULATION/'modelos'
SEED=SIMULATION/'datos_base'
DATA=ROOT/'datos/corridas'
EXPORTS=ROOT/'resultados/exportaciones'
for folder in [DATA,EXPORTS,ROOT/'logs',ROOT/'documentacion']:folder.mkdir(parents=True,exist_ok=True)
