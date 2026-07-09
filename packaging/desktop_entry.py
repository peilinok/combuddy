import multiprocessing
from combuddy.desktop import run_desktop

if __name__ == "__main__":
    multiprocessing.freeze_support()     # required for Windows onefile
    raise SystemExit(run_desktop())
