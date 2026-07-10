import multiprocessing
from combuddy.desktop import run_desktop

if __name__ == "__main__":
    multiprocessing.freeze_support()     # required for Windows onefile
    try:
        raise SystemExit(run_desktop())
    except SystemExit:
        raise
    except BaseException:                # windowed 构建:未预期异常也要留痕+提示,不静默闪退
        import traceback
        from combuddy.desktop import _fatal
        _fatal("combuddy failed to start:\n" + traceback.format_exc())
        raise SystemExit(1)
