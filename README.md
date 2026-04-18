# Smoke Detection Simulation System

Aircraft cargo bay smoke diffusion simulation with ML-based detector response prediction.

## Quick Start

```bash
pip install PySide6 pandas numpy scikit-learn matplotlib

cd ~/smoke_project
python gui_pyside6_winstyle.py
```

## Project Structure (v5.0)

| File | Description |
|------|-------------|
| `gui_pyside6_winstyle.py` | Main GUI (PySide6, Windows Classic UI) |
| `simulation.py` | Core simulation engine (GUI-decoupled) |
| `simulation_config.py` | Typed config with validation |
| `result_manager.py` | Timestamped result file manager |
| `sklearn_compat.py` | Legacy sklearn model compatibility |
| `Detector.py` | Smoke detector model |
| `cargobay.py` | Cargo bay geometry model |
| `inputs.json` | Simulation configuration |
| `rf_model.model` | Trained ML prediction model |
| `docs/development-documentation.md` | Full development documentation |

## Configuration

Edit `inputs.json` or use the Settings tab in the GUI:

- **SD_num**: Number of detectors (must be even)
- **bay_dimension**: Cargo bay [width, length, height] in mm
- **criteria**: Alarm threshold in seconds
- **arrange**: Detector layout (center or side method)

## Programmatic Usage

```python
from sklearn_compat import load_model
from simulation_config import SimulationConfig
from simulation import SimulationEngine, GridScanCallbacks
from result_manager import ResultManager

cfg  = SimulationConfig.from_json("inputs.json")
pred = load_model("rf_model.model")
rm   = ResultManager(output_dir="results")
eng  = SimulationEngine(cfg, pred, result_manager=rm)

results = eng.run_grid()
df = rm.latest_dataframe
```

## Development Documentation

See [`docs/development-documentation.md`](docs/development-documentation.md) for:
- Full module specifications
- Architecture diagrams
- Data dictionary
- Build & deployment guide
