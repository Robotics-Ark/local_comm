import sys
from io import BytesIO
from PIL import Image  # pip install pillow
import local_comm as lc


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} INPUT_FILENAME OUTPUT_FILENAME")
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
