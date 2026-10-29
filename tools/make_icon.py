"""Draw assets/icon.ico (the orange 'T' used for the window and the .exe).

No image libraries needed: the icon is written as an ICO file with 32-bit
bitmaps at 16, 24, 32, 48 and 64 pixels.
"""

import os
import struct

ORANGE = (0xcf, 0x6a, 0x32)
DARK = (0x1e, 0x1f, 0x22)
WHITE = (0xff, 0xff, 0xff)


def pixel(x, y, n):
    """Colour at (x, y) of an n*n icon: dark border, orange tile, white T."""
    edge = max(1, n // 16)
    if x < edge or y < edge or x >= n - edge or y >= n - edge:
        return DARK
    bar_top, bar_bottom = round(n * 0.22), round(n * 0.36)
    stem_left, stem_right = round(n * 0.42), round(n * 0.58)
    if bar_top <= y < bar_bottom and round(n * 0.22) <= x < round(n * 0.78):
        return WHITE
    if bar_bottom <= y < round(n * 0.80) and stem_left <= x < stem_right:
        return WHITE
    return ORANGE


def bitmap(n):
    header = struct.pack('<IiiHHIIiiII', 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = []
    for y in range(n - 1, -1, -1):            # bitmaps are stored bottom-up
        rows.append(b''.join(bytes((b, g, r, 255)) for r, g, b in (pixel(x, y, n) for x in range(n))))
    mask_row = b'\x00' * (((n + 31) // 32) * 4)
    return header + b''.join(rows) + mask_row * n


def write_ico(path, sizes=(16, 24, 32, 48, 64)):
    images = [bitmap(n) for n in sizes]
    out = struct.pack('<HHH', 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for n, data in zip(sizes, images):
        out += struct.pack('<BBBBHHII', n % 256, n % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(path, 'wb') as f:
        f.write(out + b''.join(images))


if __name__ == '__main__':
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(root, 'assets'), exist_ok=True)
    target = os.path.join(root, 'assets', 'icon.ico')
    write_ico(target)
    print('wrote', target)
