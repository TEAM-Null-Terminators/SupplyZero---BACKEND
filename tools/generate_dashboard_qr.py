"""Generate a dependency-free SVG QR code for the local SupplyZero dashboard."""
from pathlib import Path
import struct
import zlib


URL = "http://127.0.0.1:5173"
VERSION = 2  # Version 2-L holds this 22-byte URL in byte mode.
SIZE = VERSION * 4 + 17
DATA_CODEWORDS = 34
ECC_CODEWORDS = 10


def append_bits(target: list[int], value: int, count: int) -> None:
    target.extend((value >> i) & 1 for i in reversed(range(count)))


def gf_multiply(x: int, y: int) -> int:
    result = 0
    for _ in range(8):
        if y & 1:
            result ^= x
        y >>= 1
        x = (x << 1) ^ (0x11D if x & 0x80 else 0)
    return result


def error_correction(data: list[int]) -> list[int]:
    generator = [1]
    root = 1
    for _ in range(ECC_CODEWORDS):
        product = [0] * (len(generator) + 1)
        for index, coefficient in enumerate(generator):
            product[index] ^= coefficient
            product[index + 1] ^= gf_multiply(coefficient, root)
        generator = product
        root = gf_multiply(root, 2)
    remainder = data + [0] * ECC_CODEWORDS
    for index in range(len(data)):
        factor = remainder[index]
        for offset, coefficient in enumerate(generator):
            remainder[index + offset] ^= gf_multiply(coefficient, factor)
    return remainder[-ECC_CODEWORDS:]


def make_matrix() -> list[list[bool]]:
    bits: list[int] = []
    payload = URL.encode("utf-8")
    append_bits(bits, 0b0100, 4)  # byte mode
    append_bits(bits, len(payload), 8)
    for byte in payload:
        append_bits(bits, byte, 8)
    append_bits(bits, 0, min(4, DATA_CODEWORDS * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    data = [sum(bits[i + j] << (7 - j) for j in range(8))
            for i in range(0, len(bits), 8)]
    pad_bytes = (0xEC, 0x11)
    while len(data) < DATA_CODEWORDS:
        data.append(pad_bytes[(len(data) - ((len(bits) + 7) // 8)) % 2])
    all_bits = [bit for byte in data + error_correction(data)
                for bit in ((byte >> shift) & 1 for shift in reversed(range(8)))]

    matrix: list[list[bool]] = [[False] * SIZE for _ in range(SIZE)]
    function: set[tuple[int, int]] = set()

    def set_function(row: int, col: int, dark: bool) -> None:
        if 0 <= row < SIZE and 0 <= col < SIZE:
            matrix[row][col] = dark
            function.add((row, col))

    def finder(top: int, left: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                dark = (0 <= dy <= 6 and 0 <= dx <= 6 and
                        max(abs(dx - 3), abs(dy - 3)) != 2)
                set_function(top + dy, left + dx, dark)

    finder(0, 0)
    finder(0, SIZE - 7)
    finder(SIZE - 7, 0)

    for i in range(8, SIZE - 8):
        set_function(6, i, i % 2 == 0)
        set_function(i, 6, i % 2 == 0)

    # Version 2 has one alignment pattern, centered at module (18, 18).
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            set_function(18 + dy, 18 + dx, max(abs(dx), abs(dy)) != 1)

    format_a = ([(i, 8) for i in range(6)] + [(7, 8), (8, 8), (8, 7)] +
                [(8, 14 - i) for i in range(9, 15)])
    format_b = ([(8, SIZE - 1 - i) for i in range(8)] +
                [(SIZE - 15 + i, 8) for i in range(8, 15)])
    for row, col in format_a:
        set_function(row, col, False)
    for row, col in format_b:
        set_function(row, col, False)
    set_function(SIZE - 8, 8, True)

    bit_index = 0
    upward = True
    right = SIZE - 1
    while right >= 1:
        if right == 6:
            right -= 1
        for vert in range(SIZE):
            row = SIZE - 1 - vert if upward else vert
            for col in (right, right - 1):
                if (row, col) in function:
                    continue
                dark = bool(all_bits[bit_index]) if bit_index < len(all_bits) else False
                bit_index += 1
                # Mask pattern 0: (row + column) is even.
                matrix[row][col] = dark ^ ((row + col) % 2 == 0)
        upward = not upward
        right -= 2

    # Format information: error correction L (01), mask 0, BCH(15,5).
    format_data = 0b01000
    remainder = format_data << 10
    for bit in range(14, 9, -1):
        if (remainder >> bit) & 1:
            remainder ^= 0x537 << (bit - 10)
    format_bits = ((format_data << 10) | remainder) ^ 0x5412
    for bit in range(15):
        dark = ((format_bits >> bit) & 1) != 0
        row, col = format_a[bit]
        matrix[row][col] = dark
        row, col = format_b[bit]
        matrix[row][col] = dark
    matrix[SIZE - 8][8] = True
    return matrix


def png_chunk(name: bytes, data: bytes) -> bytes:
    payload = name + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def main() -> None:
    matrix = make_matrix()
    quiet = 4
    scale = 12
    dimension = (SIZE + quiet * 2) * scale
    squares = []
    for row, line in enumerate(matrix):
        for col, dark in enumerate(line):
            if dark:
                squares.append(
                    f"<rect x=\"{(col + quiet) * scale}\" y=\"{(row + quiet) * scale}\" "
                    f"width=\"{scale}\" height=\"{scale}\"/>"
                )
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{dimension}" '
           f'height="{dimension}" viewBox="0 0 {dimension} {dimension}" '
           f'role="img" aria-label="QR code for SupplyZero dashboard">'
           f'<rect width="100%" height="100%" fill="#fff"/>'
           f'<g fill="#104f3e">{"".join(squares)}</g></svg>')
    output = Path(__file__).resolve().parents[1] / "frontend" / "public" / "supplyzero-dashboard-qr.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    png_output = output.with_suffix(".png")
    pixels = bytearray()
    for y in range(dimension):
        pixels.append(0)  # PNG filter: None
        row = y // scale - quiet
        for x in range(dimension):
            col = x // scale - quiet
            dark = 0 <= row < SIZE and 0 <= col < SIZE and matrix[row][col]
            pixels.extend((16, 79, 62) if dark else (255, 255, 255))
    header = struct.pack(">IIBBBBB", dimension, dimension, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) +
           png_chunk(b"IDAT", zlib.compress(bytes(pixels), 9)) + png_chunk(b"IEND", b""))
    png_output.write_bytes(png)
    print(f"Wrote {output} and {png_output} for {URL}")


if __name__ == "__main__":
    main()
