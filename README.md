# Touchdown Football patch

A small BPS patch for the Atari 7800 game Touchdown Football (1988). It fixes field-goal scoring while preserving the game's height check and allowing the ball to finish its flight before the result appears. It also adjusts the probability of blocked extra points, which are far too common in the original version.

## Background

My dad and I used to play this game all the time. It's not the best football video game ever, or even the best 8-bit football game ever, but the Atari 7800 was the only system we had, and we had a lot of fun. However, we noticed that no matter what we tried, field goals would never work. We even took the game back to Toys 'R Us and exchanged it for another copy, hoping that our copy was bad. (I knew enough about computer programming at the time to realize that was unlikely, but it was worth a shot, and I'd never say no to a trip to Toys 'R Us.)

Years later I'd look up the game on the internet, and unsurprisingly I was not the only person who noticed that field goals would never score. I didn't know how to disassemble and read an Atari 7800 ROM though, so the "why?" would remain a mystery. Using Codex, I decided to finally figure it out, and I figured I might as well make a patch too. While I was working on it, I decided to research and fix another issue: blocked extra points are way too common.

## What the patch does

- **Field goals:** awards three points when the ball reaches the scoring boundary at sufficient height. Short or low kicks remain no good.
- **Extra points:** keeps the original ten-unit defender proximity window, but a nearby defender raises the nominal blocking chance to 25% instead of guaranteeing a block. Without a nearby defender, the original 12.5% first-gate chance remains. The separate seven-good/one-miss trajectory table is preserved.
- **Options text:** changes `1O Minute Quarters` to `10 Minute Quarters` and removes the diagonal slash from the options/title font's zero glyph.

## Download and apply

Download [Touchdown-Football-patch.bps](patches/Touchdown-Football-patch.bps) and apply it to your clean original `.a78` ROM with a BPS-compatible patcher. Or, you know, just have your AI thing do it.

The expected input is **131,200 bytes**: a 128-byte A78 header plus a 128 KiB ROM payload. Its SHA-256 must be:

```text
1d7114a709d2fa0e21ae95b00adda93595283def16dbea981924c1e0ff47df27
```

Save the result as an `.a78` file and run it like you would run any other Atari 7800 ROM. No original or patched game ROM is distributed.

## Documentation and validation

The [technical writeup](FIELD_GOAL_FIX_WRITEUP.md) explains the original bug, the scoring and flight implementation, the extra-point adjustment, and the investigation. It includes a brief comparison with an earlier implementation. It was mostly written by Codex.

The field-goal implementation has been played in RetroArch with ProSystem on Linux x64 and Wii U/Aroma, including successful kicks in both directions and short kicks called no good. The text and font changes were also checked in gameplay. The extra-point probability adjustment passed 3,584 controlled CPU cases and was also tested in gameplay, with both successful and missed attempts observed. These checks do not establish compatibility with every emulator or real Atari 7800 hardware.

## Rebuild

Python 3.10 or later is sufficient; no extra Python packages are needed.

```sh
python3 tools/build_release.py original.a78 patched.a78 patches/Touchdown-Football-patch.bps
```

The script checks the source hash and original bytes, constructs the patched ROM directly, verifies its expected hash, and applies the generated BPS patch back to the source to check that it reproduces the same ROM exactly.

## Checksums

```text
BPS patch SHA-256:   fd4fe1a10f13d6568ffccc9216832998e64a26a05dfff42277fffc4adbd520ad
Patched ROM SHA-256: c53b371c140030e3b82c0cce1dff590b8b575e390250241531e9c81598c1d8e9
```

## Future

This has been a lot of fun, and I might mess with it more in the future. Selectable team colors?
