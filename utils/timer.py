from time import perf_counter


class Timer:

    def __init__(self, label):
        self.label = label

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, *args):
        end = perf_counter()
        elapsed = end - self.start

        print(
            f"⏱ {self.label:<25} "
            f"{elapsed:8.2f} s"
        )