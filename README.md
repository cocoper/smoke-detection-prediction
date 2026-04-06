# Smoke Detection Simulation System

Aircraft cargo bay smoke diffusion simulation with ML-based detector response prediction.

## Quick Start

```bash
# Install dependencies
pip install PySide6 pandas numpy scikit-learn matplotlib

# Run the GUI (Windows Classic style)
cd ~/smoke_project
python gui_pyside6_winstyle.py
```

## Project Structure

| File | Description |
|------|-------------|
| `gui_pyside6_winstyle.py` | Main GUI application (PySide6, Windows Classic UI) |
| `gui_pyside6_v3.py` | Previous GUI version |
| `Detector.py` | Smoke detector model |
| `CargoBay.py` | Cargo bay geometry model |
| `Environment.py` | Simulation engine |
| `inputs.json` | Simulation configuration |
| `rf_model.model` | Trained ML prediction model |
| `docs/development-documentation.md` | Full development documentation |

## Configuration

Edit `inputs.json` to set:
- Cargo bay dimensions (`bay_dimension`)
- Number of detectors (`SD_num`)
- Arrangement method (`center` or `side`)
- Alarm time threshold (`criteria`, seconds)

## Development Documentation

See [`docs/development-documentation.md`](docs/development-documentation.md) for:
- Class and function specifications
- Data dictionary
- Architecture diagrams
- API reference
- Build & deployment guide
