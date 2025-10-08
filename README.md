# 🧩 local_comm

> **A lightweight, zero-dependency Python library for ultra-fast local inter-process communication (IPC)**  
> Built on **shared memory** 🧠 and **Unix domain sockets** 🔌 for blazing-fast data exchange between processes on the same Linux machine.

---

## 🚀 Features

- ⚡ **Zero-copy** shared memory for high-throughput transfers  
- 🧱 **Pure standard library** — no external dependencies (Python ≥ 3.8)  
- 🔄 **Request–response RPC model**
- 🖼️ **Binary-safe** — easily send images, tensors, or serialized objects  
- 🧠 **Perfect for ML pipelines** where modules need to exchange large data locally  

---

## 🛠️ Installation

```bash
# Clone the repo
git clone https://github.com/cmower/local_comm.git
cd local_comm

# Install the package
pip install .
```

> 💡 Requires Linux and Python 3.8 or newer.

## 📦 Example Usage

Example scripts are available in the `examples/` directory.

### 🧠 Server (`examples/server.py`)

```python
import local_comm as lc
from io import BytesIO
from PIL import Image, ImageOps  # pip install pillow

def callback(data_in: bytes) -> bytes:
    """Invert image colors and return as PNG bytes."""
    img = Image.open(BytesIO(data_in)).convert("RGB")
    inverted = ImageOps.invert(img)
    buf = BytesIO()
    inverted.save(buf, format="PNG")
    return buf.getvalue()

def main():
    ep = lc.EndPoint()
    ep.create_service("invert_image", callback)
    print("[server] Ready on service 'invert_image' (Ctrl+C to stop)")
    ep.spin()

if __name__ == "__main__":
    main()
```

### 📸 Client (`examples/client.py`)

```python
import sys
from io import BytesIO
from PIL import Image  # pip install pillow
import local_comm as lc

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.jpg output.png")
        sys.exit(2)

    input_path, output_path = sys.argv[1], sys.argv[2]
    ep = lc.EndPoint()
    srv = ep.create_service_caller("invert_image")

    # Load image -> PNG bytes
    img = Image.open(input_path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    data_in = buf.getvalue()

    print(f"[client] Sending {len(data_in)/1e6:.2f} MB image...")
    data_out = srv.call(data_in)

    # Save response
    out_img = Image.open(BytesIO(data_out))
    out_img.save(output_path)
    print(f"[client] Wrote inverted image to {output_path}")

if __name__ == "__main__":
    main()
```

### ▶️ Running the Examples

```
# Terminal 1: run the server
python examples/server.py

# Terminal 2: run the client
python examples/client.py input_image output_image
```

> Try running the client and server in different conda environments with different Python versions! :smile:
> 
> Also try the even simpler examples! 😆 See `examples/simple_server.py` and `examples/simple_client.py` that are completely dependancy free. 

## 🧪 Performance Test

A standalone benchmark is included in `test/test.py`.

Run it to measure latency and throughput for synthetic image sizes:
```
python test/test.py
```

## 🧱 Project Structure

```
local_comm
├── examples
│   ├── client.py
│   └── server.py
├── LICENSE
├── local_comm
│   ├── __init__.py
│   └── _local_comm.py
├── pyproject.toml
├── README.md
└── test
    └── test.py

```

## 🧑‍💻 Author & License
* 🧔 Author: Christopher E. Mower
* 📜 License: MIT

## 💡 Tip

Use `local_comm` to bridge isolated environments — e.g. machine learning modules with conflicting dependencies — without network overhead or containers.
Just plug them together via `local_comm`'s shared memory IPC.

> 🧠 Think of it as a "local RPC over shared memory" — tiny, fast, and dependency-free.

## ⭐ Like it?

If you find this project useful:
* ⭐ Please Star it on GitHub
* 🐛 Open issues for feedback or bugs
* 🤝 Contribute new examples or features!
