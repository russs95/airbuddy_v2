# convert_logo.py
from PIL import Image

IN_FILE = "airbuddy_logo_128x24.png"
OUT_FILE = "logo_airbuddy.py"

img = Image.open(IN_FILE).convert("1")  # 1-bit
img = img.transpose(Image.FLIP_TOP_BOTTOM)  # SSD1306 VLSB fix
img = Image.eval(img, lambda p: 255 - p)  # invert (logo = white)

w, h = img.size
data = bytearray()

pixels = img.load()
for y in range(0, h, 8):
    for x in range(w):
        byte = 0
        for bit in range(8):
            if y + bit < h and pixels[x, y + bit]:
                byte |= (1 << bit)
        data.append(byte)

with open(OUT_FILE, "w") as f:
    f.write("WIDTH = %d\n" % w)
    f.write("HEIGHT = %d\n" % h)
    f.write("DATA = bytes(%r)\n" % bytes(data))

print("Written", OUT_FILE)
