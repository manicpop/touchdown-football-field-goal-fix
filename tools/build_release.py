#!/usr/bin/env python3
"""Build the patched ROM and BPS patch from a verified original A78 image."""
from hashlib import sha256
from pathlib import Path
import struct
import sys
import zlib

SOURCE_SHA256 = "1d7114a709d2fa0e21ae95b00adda93595283def16dbea981924c1e0ff47df27"
TARGET_SHA256 = "c53b371c140030e3b82c0cce1dff590b8b575e390250241531e9c81598c1d8e9"
HEADER_SIZE = 128
BANK_SIZE = 0x4000


def rom_offset(cpu_address: int, bank: int) -> int:
    return HEADER_SIZE + bank * BANK_SIZE + cpu_address - (0xC000 if bank == 7 else 0x8000)


def put(rom: bytearray, offset: int, expected: bytes, replacement: bytes) -> None:
    if rom[offset:offset + len(expected)] != expected:
        raise ValueError(f"unexpected ROM bytes at file offset ${offset:X}")
    rom[offset:offset + len(replacement)] = replacement


def bps_number(value: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = value & 0x7F
        value >>= 7
        if value == 0:
            encoded.append(digit | 0x80)
            return bytes(encoded)
        encoded.append(digit)
        value -= 1


def make_bps(source: bytes, target: bytes) -> bytes:
    if len(source) != len(target):
        raise ValueError("this release expects equal-size source and target ROMs")
    patch = bytearray(b"BPS1")
    patch += bps_number(len(source))
    patch += bps_number(len(target))
    patch += bps_number(0)  # No patch metadata.

    pos = 0
    while pos < len(target):
        same = source[pos] == target[pos]
        end = pos + 1
        while end < len(target) and (source[end] == target[end]) == same:
            end += 1
        length = end - pos
        patch += bps_number(((length - 1) << 2) | (0 if same else 1))
        if not same:  # TargetRead stores only modified bytes.
            patch += target[pos:end]
        pos = end

    patch += struct.pack("<II", zlib.crc32(source), zlib.crc32(target))
    patch += struct.pack("<I", zlib.crc32(patch))
    return bytes(patch)


def bps_read_number(patch: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        digit = patch[offset]
        offset += 1
        value += (digit & 0x7F) * shift
        if digit & 0x80:
            return value, offset
        shift <<= 7
        value += shift


def check_bps(source: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1" or zlib.crc32(patch[:-4]) != struct.unpack("<I", patch[-4:])[0]:
        raise ValueError("invalid BPS header or patch CRC")
    action_end = len(patch) - 12
    offset = 4
    source_size, offset = bps_read_number(patch, offset)
    target_size, offset = bps_read_number(patch, offset)
    metadata_size, offset = bps_read_number(patch, offset)
    if source_size != len(source):
        raise ValueError("BPS source size does not match input ROM")
    offset += metadata_size
    output = bytearray()
    while offset < action_end and len(output) < target_size:
        command, offset = bps_read_number(patch, offset)
        length, mode = (command >> 2) + 1, command & 3
        if mode == 0:  # SourceRead copies from the same offset.
            start = len(output)
            output += source[start:start + length]
        elif mode == 1:  # TargetRead contains literal target data.
            output += patch[offset:offset + length]
            offset += length
        else:
            raise ValueError(f"unexpected BPS action mode {mode}")

    source_crc, target_crc = struct.unpack("<II", patch[action_end:action_end + 8])
    if len(output) != target_size or offset != action_end:
        raise ValueError("invalid BPS action stream")
    if zlib.crc32(source) != source_crc or zlib.crc32(output) != target_crc:
        raise ValueError("BPS source or target CRC mismatch")
    return bytes(output)


def patch_rom(source: bytes) -> bytes:
    """Reproduce the playable candidate directly; no intermediate ROMs needed."""
    if len(source) != HEADER_SIZE + 8 * BANK_SIZE:
        raise ValueError("expected a 128 KiB ROM with a 128-byte A78 header")
    if sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("source ROM SHA-256 does not match the required original")
    rom = bytearray(source)
    # Retain the cartridge header used by the PC/Wii U tested base.
    put(rom, 54, b"\x02", b"\x08")

    # Options text: ASCII capital O -> zero in '10 Minute Quarters'.
    put(rom, rom_offset(0x80AB, 0), b"O", b"0")
    # Keep the zero's outline, clearing its six diagonal slash pixels.
    for address, expected in [(0x8930, 0xE6), (0x8A30, 0xF6),
                              (0x8B30, 0xDE), (0x8C30, 0xCE)]:
        put(rom, rom_offset(address, 0), bytes([expected]), b"\xC6")

    # Result state enters the bank-2 field-coordinate/deferred-banner handler.
    put(rom, rom_offset(0x9658, 2), bytes.fromhex("A5 75 C9 FF F0 05 A5 79 F0 33 60"),
        bytes.fromhex("4C 00 BE") + b"\xEA" * 8)
    # Bit 0 of $211B remains the launch flag; bit 1 means scored-good pending,
    # bit 2 means miss pending. Score at X<1 or X>=110 with height>=10, then
    # keep state $1F and physics active until clipping ($75=FF) or flight ends.
    # Only then run the original good/miss banner and state transition.
    field_goal_handler = bytes.fromhex(
        "AD 1B 21 29 06 D0 33 A5 72 C9 01 90 16 C9 6E B0"
        "12 A5 75 C9 FF F0 1D A5 79 D0 5B AD 88 25 D0 56"
        "4C 95 96 A5 79 C9 0A 90 0B A9 03 20 27 D0 A9 03"
        "8D 1B 21 60 A9 05 8D 1B 21 60 A5 75 C9 FF F0 05"
        "AD 88 25 D0 31 AD 1B 21 29 02 D0 03 4C 95 96 20"
        "99 90 A9 00 8D 88 25 8D A4 25 20 54 D0 A9 04 20"
        "D5 B3 A9 20 85 5F A9 28 8D 4F 25 A9 06 20 4B D0"
        "A9 00 8D 14 21 60 60"
    )
    put(rom, rom_offset(0xBE00, 2), b"\xFF" * len(field_goal_handler), field_goal_handler)

    # Original proximity scan and threshold 10 remain. Carry chooses 25% close
    # versus 12.5% far at the first gate; the second trajectory table is intact.
    put(rom, rom_offset(0x935E, 2), bytes.fromhex("B0 0A 20 54 D0 AD 94 25 29 07 D0 1E"),
        bytes.fromhex("4C 80 BE") + b"\xEA" * 9)
    extra_point_gate = bytes.fromhex(
        "B0 0D "           # BCS close ($BE8F), retaining proximity carry
        "20 54 D0 "        # far: advance PRNG
        "AD 94 25 29 07 "  # 1/8 first-gate block chance
        "4C 97 BE EA EA "  # jump to decision; padding
        "20 54 D0 "        # close: advance PRNG
        "AD 94 25 29 03 "  # 1/4 first-gate block chance
        "F0 03 4C 88 93 "  # nonzero -> original second draw/table at $9388
        "4C 6A 93"         # zero -> original blocked/miss path at $936A
    )
    put(rom, rom_offset(0xBE80, 2), b"\xFF" * len(extra_point_gate), extra_point_gate)

    # Preserve the unused-bank byte carried by the PC/Wii U tested base.
    # Bank 4 is otherwise FF-filled; this is not executed kick logic.
    put(rom, rom_offset(0xBFFF, 4), b"\xFF", b"\xEA")
    return bytes(rom)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: build_release.py ORIGINAL.a78 OUTPUT.a78 OUTPUT.bps")
    source_path, output_path, patch_path = map(Path, sys.argv[1:])
    source = source_path.read_bytes()
    if sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("source ROM SHA-256 does not match the required original")
    target = patch_rom(source)
    if sha256(target).hexdigest() != TARGET_SHA256:
        raise SystemExit("built ROM SHA-256 differs from the tested release")
    patch = make_bps(source, target)
    if check_bps(source, patch) != target:
        raise SystemExit("BPS self-check failed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(target)
    patch_path.write_bytes(patch)
    print(f"Patched ROM: {output_path} ({sha256(target).hexdigest()})")
    print(f"BPS patch:   {patch_path} ({sha256(patch).hexdigest()})")
    print("BPS reconstructed the tested ROM successfully.")


if __name__ == "__main__":
    main()
