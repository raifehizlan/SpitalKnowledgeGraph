# Swiss Hospital Intelligence

Graubünden pilot. The screen reads `data/pilot.sqlite` and projects it into a graph. SPARQL questions run on that projection. Department names come from the three Graubünden Spitalliste PDFs. A billing code stays a mandate beside the graph.

## Run the screen

The pilot is already in `data/pilot.sqlite`. Docker is not required. Python 3.11 or newer is required. The screen opens at http://localhost:8502.

### Windows

`run.bat` creates the environment, installs the packages, and starts the screen.

```powershell
run.bat
```

The same steps by hand:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m streamlit run frontend/app.py --server.port 8502
```

### Mac

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m streamlit run frontend/app.py --server.port 8502
```

