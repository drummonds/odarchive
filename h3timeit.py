import datetime as dt
import time


def h3_timeit(method):

    def timed(*args, **kw):
        ts = time.time()
        print(f"timeit started {dt.datetime.now()}")
        try:
            result = method(*args, **kw)
        finally:
            te = time.time()

            if "log_time" in kw:
                name = kw.get("log_name", method.__name__.upper())
                kw["log_time"][name] = int((te - ts) * 1000)
            else:
                print("%r  %2.3f s" % (method.__name__, (te - ts)))
        return result

    return timed
