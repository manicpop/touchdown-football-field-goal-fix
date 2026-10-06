#!/usr/bin/env python3
"""Build the patched ROM and BPS patch from a verified original A78 image."""
from hashlib import sha256
from pathlib import Path
import struct
import sys
import zlib

SOURCE_SHA256 = "1d7114a709d2fa0e21ae95b00adda93595283def16dbea981924c1e0ff47df27"
TARGET_SHA256 = "df88503356731920310dc0bd5ce09ce3072247048ac50aa34709667279813eef"
HEADER_SIZE = 128
BANK_SIZE = 0x4000


def rom_offset(cpu_address: int, bank: int) -> int:
    return HEADER_SIZE + bank * BANK_SIZE + cpu_address - (0x8000 if bank == 2 else 0xC000)


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
    if len(source) != 128 + 8 * BANK_SIZE:
        raise ValueError("expected a 128 KiB ROM with a 128-byte A78 header")
    if source[54] != 0x02:
        raise ValueError("unexpected source mapper header byte")

    rom = bytearray(source)
    # Explicitly encode the mapper ProSystem assigns to the original ROM.
    rom[54] = 0x12

    # Keep rendering scratch $96, and also publish the projected X into $75.
    put(rom, rom_offset(0xD62D, 7), bytes.fromhex("A5 96 38 E9 01 85 96"),
        bytes.fromhex("4C 0C DE EA EA EA EA"))

    # Treat the projected 160-pixel edge as the off-screen scoring threshold.
    result = rom_offset(0x965A, 2)
    put(rom, result, bytes.fromhex("C9 FF F0"), bytes.fromhex("C9 A0 B0"))

    # Set $75=$FF on the renderer's coarse clip path and retain its cleanup.
    put(rom, rom_offset(0xD5E7, 7), bytes.fromhex("20 0F 60"), bytes.fromhex("4C 00 DE"))
    put(rom, rom_offset(0xDE00, 7), b"\xFF" * 12,
        bytes.fromhex("48 A9 FF 85 75 68 20 0F 60 4C EA D5"))
    put(rom, rom_offset(0xDE0C, 7), b"\xFF" * 12,
        bytes.fromhex("A5 96 38 E9 01 85 96 85 75 4C 34 D6"))
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
