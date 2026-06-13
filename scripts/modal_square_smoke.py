import modal


app = modal.App("tiny-toybox-modal-smoke")


@app.function()
def square(x: int) -> int:
    print("Tiny Toybox Modal smoke test is running remotely.")
    return x * x


@app.local_entrypoint()
def main() -> None:
    result = square.remote(42)
    print("modal_square_result", result)
    if result != 1764:
        raise RuntimeError(f"Unexpected Modal result: {result}")
