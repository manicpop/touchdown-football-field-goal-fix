# Touchdown Football field-goal fix

A small BPS patch for the Atari 7800 game *Touchdown Football* (1988). It
restores field-goal scoring while preserving the game's height check and
extra-point behavior.

## Download and apply

Download [`Touchdown-Football-field-goal-fix-v1.bps`](patches/Touchdown-Football-field-goal-fix-v1.bps)
and apply it to your own clean `.a78` ROM with a BPS-compatible patcher.
The expected input is the 128 KiB ROM extracted from the original archive and
has SHA-256:

```text
1d7114a709d2fa0e21ae95b00adda93595283def16dbea981924c1e0ff47df27
```

Save the patched output as an `.a78` file and load it in your Atari 7800
emulator. The patch changes the cartridge mapper bits so the modified image
works even when its hash is not in the emulator's game database.

## What is fixed

The field-goal result code waited for an off-screen marker that the ball
renderer never wrote. The patch records the ball's projected screen position,
sets the marker on the off-screen path, and checks that the ball is high enough
at the screen edge. See the [full technical writeup](FIELD_GOAL_FIX_WRITEUP.md)
for the ROM analysis, exact changes, tests, and known limits.

## Gameplay checks

- Field goals scored three points from both directions in RetroArch with the
  ProSystem core.
- A long kick that landed before the goalposts was no good.
- A blocked extra point was no good.

This covers the reported defect and nearby outcomes, not every possible kick.

## Checksums

```text
BPS patch SHA-256: 06b3259cc1dd9ce7b6a59af7f24969d31e36d49984514d767b005320b7630139
Patched ROM SHA-256: df88503356731920310dc0bd5ce09ce3072247048ac50aa34709667279813eef
```

The original game ROM is not included.
