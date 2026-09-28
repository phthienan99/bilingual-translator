import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
def create_app():
    from server import app
    return app
