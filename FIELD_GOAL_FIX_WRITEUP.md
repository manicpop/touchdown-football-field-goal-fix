# Touchdown Football field-goal fix

## Summary

The original Touchdown Football ROM could complete an extra-point attempt, but
field goals always ended as no good. The field-goal result handler waits for
RAM byte `$75` to indicate that the ball has gone off screen. In the original
gameplay code, the ball renderer calculated its projected screen X in scratch
byte `$96` but never copied that value—or an off-screen marker—to `$75`. The
field-goal handler therefore did not see the event it was waiting for.

The patch connects the ball renderer to that existing result check. It stores
the projected screen X in `$75`, marks the ball `$FF` on the renderer's early
off-screen path, and lets the field-goal handler recognize screen positions at
or beyond `$A0` (160 pixels). The existing height check still determines
whether the ball cleared the posts. A successful kick awards the game's
existing three points.

The fix is distributed as the BPS patch
[`Touchdown-Football-field-goal-fix-v1.bps`](patches/Touchdown-Football-field-goal-fix-v1.bps).
Application instructions and checksums are in the repository [README](README.md).

## What the original code does

The field-goal result routine is at bank 2 address `$9658`. It first compares
`$75` with `$FF`:

```text
if $75 == $FF:
    if ball height $79 >= $0A: score 3 points
    else: report NO GOOD
else:
    wait while $79 is nonzero
    report NO GOOD when the ball reaches ground level
```

So `$75` is a gate into the only successful branch. If it never becomes `$FF`,
the ball can travel through a visually successful arc and the routine will
still wait for it to land, then report no good.

The ball renderer at fixed-bank address `$D5F7` calculates the ball's screen
position from its world coordinates and the camera offset. It projects the
horizontal coordinate into scratch `$96`, then adjusts `$96` by one pixel for
the display call. Unlike the parallel player renderer, it does not save a
persistent screen-X value or `$FF` off-screen marker in `$75`. The original
ROM initializes `$75` to zero but has no gameplay update for it in this ball
rendering path.

Extra points use different outcome logic, including the preselected result
index at `$211F`. The patch does not change that logic. A blocked extra point
continues to be a miss.

## What the patch changes

### 1. Keep the ball screen position without disturbing rendering

On the visible-ball path, the patch redirects the code at `$D62D` to a small
routine in unused fixed-bank space. That routine performs the original
subtraction and stores the resulting display coordinate back into `$96`,
preserving the renderer's scratch value. It then copies the same coordinate to
`$75` and resumes the original renderer at `$D634`.

Preserving `$96` matters: it is shared display scratch. An early candidate
replaced `STA $96` with `STA $75`; that broke unrelated drawing behavior and
was discarded. The released patch keeps the original `$96` write.

### 2. Mark the early off-screen path

When the renderer rejects the ball before projection, it already runs display
cleanup at `$D5E7`. The patch routes that path through a short trampoline that
sets `$75` to `$FF`, preserves the accumulator, performs the original cleanup,
and returns to the original code. This supplies the same kind of off-screen
sentinel used elsewhere in the game.

### 3. Recognize the projected screen edge

For visible positions, `$75` now contains a coordinate rather than only a
Boolean result. The field-goal comparison changes from:

```asm
CMP #$FF
BEQ $9663
```

to:

```asm
CMP #$A0
BCS $9663
```

The scoring path therefore begins when the projected horizontal coordinate is
at least `$A0`, the 160-pixel screen edge, or when the off-screen renderer has
set `$75` to `$FF`. The original `$79 >= $0A` altitude requirement is
unchanged. A low or short ball still reaches the NO GOOD path.

### 4. Set the cartridge mapper in the patched header

The original ROM is recognized by ProSystem's built-in database, which
assigns it mapper type 4. Once the ROM bytes change, that database hash no
longer matches. The original A78 header byte `$02` falls back to another mapper
type in the ProSystem core. The patch changes header byte 54 to `$12`, encoding
the SuperGame and bank-6-at-`$4000` flags that make this core select mapper type
4 without a database entry. This is needed for the patched ROM to start and
bank-switch correctly in RetroArch.

## How the cause was identified

The investigation compared the extra-point and field-goal result paths, traced
all ROM code that reads or writes `$75`, and followed the ball's rendering
routine. That showed the field-goal handler depended on `$75 == $FF`, while
the renderer had the screen coordinate available in `$96` but did not publish
it to `$75`. Controlled emulator runs then showed that supplying the missing
screen-position value made otherwise identical kicks reach the existing good
branch when they were high enough at the screen edge.

The interpretation of `$75` as persistent ball screen X is strongly supported
by the renderer structure and the field-goal check, but it is inferred from
the ROM rather than confirmed from the original source code. Likewise, `$A0`
is the renderer-derived screen edge; it is not a recovered, exact goalpost
coordinate.

## Testing

The patched ROM was tested in RetroArch with the ProSystem core. Gameplay
checks confirmed:

- A field goal scored three points from one direction.
- A field goal also scored three points from the other direction.
- A long kick that hit the ground before reaching the posts was no good.
- A blocked extra point was no good.

Controlled emulator runs confirmed that a camera-aligned kick can reach the
existing good path with the height threshold satisfied. A 50,000-frame
extra-point comparison retained the same outcome sequence in the original and
patched images. These tests cover the reported defect and nearby outcomes;
they do not cover every trajectory, distance, or game situation.

## Rebuilding and identifying the release

The candidate ROM is generated by:

```sh
python3 tools/build_release.py original.a78 patched.a78 patches/Touchdown-Football-field-goal-fix-v1.bps
```

The release BPS patch is built and self-verified by:

```sh
python3 tools/build_release.py original.a78 patched.a78 patches/Touchdown-Football-field-goal-fix-v1.bps
```

The BPS patch expects the original 128 KiB `.a78` ROM with SHA-256
`1d7114a709d2fa0e21ae95b00adda93595283def16dbea981924c1e0ff47df27`. The
released patch SHA-256 is
`06b3259cc1dd9ce7b6a59af7f24969d31e36d49984514d767b005320b7630139`. It
reconstructs the tested ROM with SHA-256
`df88503356731920310dc0bd5ce09ce3072247048ac50aa34709667279813eef`.
