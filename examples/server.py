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
