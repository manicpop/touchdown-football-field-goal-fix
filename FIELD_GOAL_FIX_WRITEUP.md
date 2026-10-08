# Touchdown Football patch: technical writeup

## The problem

In the original Atari 7800 *Touchdown Football*, extra points can succeed,
but field goals always end as `NO GOOD`. A kick can visibly travel through
the goalposts without producing three points.

The field-goal result handler at bank 2 `$9658` depends on RAM byte `$75`:

```text
if $75 == $FF:
    if ball height $79 >= $0A: score three points
    else: NO GOOD
else:
    wait while the ball is airborne
    NO GOOD when it reaches ground level
```

`$75` is initialized to zero, but the original gameplay code does not maintain
it. The ball renderer computes a projected screen X in scratch byte `$96`,
then draws the ball without publishing that coordinate or an off-screen
marker to `$75`. The parallel player renderer maintains a persistent screen
coordinate and uses `$FF` for clipping. That strongly supports the interpretation
that `$75` was meant to hold analogous ball information, although the original
source code and designers' intentions are unavailable.

Because the required `$FF` never arrives, the successful branch is unreachable.
The handler waits for the ball to land and reports a miss. The game already
contains kick trajectories, a height check, a three-point score routine, and
the `KICK GOOD` message; it is the gate into that code that is broken.

Extra points avoid that dependency: after flight ends, their result uses a
trajectory/outcome index stored at `$211F`. This is why they can work while
field goals fail.

## The field-goal repair

### Judge the ball in field coordinates

The patch redirects the result entry at `$9658` to a small handler in unused
**bank 2** space at `$BE00`. Launch and flight calculations remain the game's
own routines.

The handler checks longitudinal field coordinate `$72` against outer scoring
thresholds: below `$01`, or at least `$6E` (110). At a crossing, the original
minimum-height requirement `$79 >= $0A` determines whether the kick qualifies.
A qualifying kick calls the existing score routine at fixed `$D027` with three
points. A low crossing is recorded as a miss; landing before reaching a
boundary is also no good.

These are tested thresholds in the game's coordinate system, not a claim to
have recovered an exact original goalpost collision specification. The handler
has no explicit lateral interval check between the uprights. The original
kick generator selects lateral targets near field center and is preserved.

### Let the kick finish before its result message

Although a successful field goal is unreachable in the unmodified game, the
ROM contains a complete success branch. If the missing `$75=$FF` event were
supplied while the ball was high enough, execution would enter that branch at
`$9669`. It clears `$2588`, the flag that enables free-ball flight, displays
`KICK GOOD`, awards three points, and enters result state `$20`.

Making that branch reachable fixes scoring, but also ends the ball's flight
as soon as success is recognized. In the unmodified game, field goals instead
continue flying before the inevitable `NO GOOD`; extra points likewise finish
their flight before the result appears. Preserving that visible behavior
requires more than opening the original success branch.

The patch separates scoring from presentation. At a qualifying crossing it
awards the points once, records a pending good result, and leaves kick-flight
state `$1F` active. The ball continues under the original physics. After
flight ends, the handler displays `KICK GOOD` and enters the original result
state `$20`. A low crossing similarly records a pending miss and allows flight
to finish before the original no-good path.

Pending results occupy spare bits in existing flag `$211B`:

| Bit | Meaning |
|---|---|
| 0 | Original kick-launched flag, preserved |
| 1 | Good kick already scored; result message pending |
| 2 | Miss recorded; result message pending |

Launch sets `$211B=1`, clearing pending bits for the next attempt. Repeated
calls do not award points again or turn a recorded miss into a late success.
Completion uses flight flag `$2588`; the handler also retains a check for
`$75=$FF`. The patch does not add a `$75` producer, so normal completion is
driven by the physics ending.

## Extra-point blocking adjustment

For an extra point that reaches kick launch, the original outcome selection
has two stages:

1. A defensive-pressure/random gate can select a blocked or deflected miss.
2. If that gate passes, another random draw selects one of eight trajectory
   templates. Seven have a good result and one has a miss.

Before those stages, the original pre-launch routine at `$92FB` checks the
holder's contact flag (`$2326,holder & 2`). If it is set (that is, the
holder has been touched by the defense), `$9304` calls the
attempt no good without launching the ball or drawing either random value.
The patch preserves this contact-based failure, so the percentages below do
not apply to every extra-point attempt.

The first stage scans all six opposing players with fixed helper `$DA79`.
It compares projected screen coordinates with the **holder** `$64`; the
approaching kicker is `$68`. Both differences must be strictly below
`$212C=10`. This is a rectangular screen-coordinate test at kick launch,
not a distance in yards or a check at the snap.

A nearby defender originally **guarantees** the blocked/miss path. Otherwise,
the game draws a random byte and selects that path if its low three bits are
zero: a nominal 1-in-8 chance.

The patch keeps the ten-unit window but makes proximity increase the chance
rather than dictate the result:

| Defender proximity | First gate in the patch |
|---|---|
| Any defender within the window | Random byte AND `$03` equals zero: nominal 25% block chance |
| No defender within the window | Original random byte AND `$07` equals zero: nominal 12.5% block chance |

The original second draw, trajectory table, blocked-flight animation, and
result handling remain. Avoiding a block therefore does not guarantee a good
extra point. These percentages describe uniform random-byte outcomes at the
first gate, not the total gameplay miss rate; successive PRNG outputs are
correlated.

The gate at `$935E` jumps to a 31-byte helper at `$BE80`. The proximity call
and threshold remain. Its carry result chooses the appropriate mask before
the helper advances the generator once. Zero jumps to the original blocked
path `$936A`; nonzero jumps to the original second-draw/table path `$9388`.
The far path retains its original draw count and decision for every byte.
The helper needs no additional RAM variable.

Field goals already use similar nominal 25%-near/12.5%-far blocking, although
they check the longitudinal position of the user-controllable defender rather
than all six players. Their success depends on flight progress and height,
rather than the extra-point result table.

It is plausible that extra points' first stage was intended to model a
probability of defensive pressure separately from the second stage's accuracy.
That is a hypothesis, not a demonstrated omission in the original program.
This adjustment is an intentional balance choice, informed by field-goal
behavior and interactive observations of excessive automatic blocks.

## Text, font, and cartridge configuration

The options menu stores `1O Minute Quarters` with ASCII capital O. Bank 0
`$80AB` changes from `$4F` to `$30`, selecting zero. Four font bytes at
`$8930/$8A30/$8B30/$8C30` become `$C6`, clearing six slash pixels while
retaining the zero's outline. This affects the options/title font, not the
separate gameplay font.

Why? When I was dumping the game's text, Codex pointed out that the zero in
"10 Minute Quarters" was not a zero at all, but actually a capital O.
Changing the O to a 0 worked, but the slash through the 0 in the game's font
looked odd. The 0 shape looked better than the O, however, so I removed the
slash from the font. Rather than being a mistake, it's possible the original
developer just liked the look of the O with no slash instead of the 0, but
didn't want to change the font.

The A78 cartridge byte at file offset 54 changes from `$02` to `$08`, retaining
the configuration used by the PC and Wii U tested base. The modified ROM no
longer has the original database hash, so its header must supply a working
mapping without that recognition. The tested base also contains `$EA` instead
of `$FF` at the final byte of otherwise unused bank 4 (`$BFFF` in the banked
listing); this package preserves that byte. It is not executed kick logic,
and its independent effect has not been established.

No fixed-bank ball-renderer trampoline is installed. Both added kick handlers
reside in bank 2, already selected while the kick states execute.

## How the cause was established

The investigation compared extra-point and field-goal handlers, cataloged
original-ROM accesses to `$75`, and followed the player and ball renderers.
Controlled emulator experiments showed that supplying the missing event let
otherwise viable kicks enter the existing three-point branch. That established
the broken gate rather than an absence of field-goal code.

Following coordinates and physics supported judging kicks at a field boundary
independently of camera clipping. Interactive tests established successful
kicks in both directions and correct short-kick failures. Comparing flight
with extra points and the original unsuccessful field goals led to separating
the score event from the later banner.

Further traces identified the holder/kicker roles, extra points' two gates,
and field goals' blocking rule. The probability adjustment keeps that
two-stage structure while removing automatic close-defender failure.

### Previous implementation

The earlier published implementation approached the defect by supplying the
missing `$75` value. It hooked the ball renderer in fixed **bank 7**, using
helpers at `$DE00` and `$DE0C` to publish projected screen X or an off-screen
`$FF` marker. In **bank 2**, it changed the original result comparison to
accept values at or beyond the 160-pixel screen edge (`$A0`). That connected
the renderer to the existing height check and successful scoring branch.

On Linux, this repaired scoring: good kicks awarded three points in both
directions, and short kicks remained no good. However, success still entered
the original branch described above, ending flight when the result was
recognized. The ball did not finish its flight as it does on extra points
and unsuccessful field goals in the original game. The decision also depended
on projected screen position and camera clipping.

That implementation then failed to boot in RetroArch on Wii U/Aroma, despite
working on Linux with the same reported ProSystem version. Testing with and
without the Atari 7800 BIOS did not resolve the failure. This prompted further
mapper/header tests and a different implementation. The exact cause of the
earlier build's platform-specific failure was not established.

The resulting patch judges field coordinates directly and keeps both added
kick handlers in **bank 2**, which is already selected during the kick states.
It needs no bank-7 renderer hooks or additional bank switches in those handlers.
It also records the result separately from its presentation, letting the ball
finish flying before the banner. Together with the tested cartridge header,
this implementation boots and plays on both tested platforms. It gives us a
more direct scoring decision, the original style of kick presentation, and
broader demonstrated compatibility. The original height requirement and
three-point score routine remain in use.

## Validation and limits

The emulator builds recorded during the investigation were:

| Environment | ProSystem core identification |
|---|---|
| RetroArch on Linux x64 | Version **1.3e**, reported commit **`8a88014`** |
| RetroArch on Wii U/Aroma | Version **1.3e**, reported commit **`d9949c7`** |
| Local instrumented research core | Based on commit **`8a88014287c7a01cd568067e5a557d0a2b2a051f`**, with local tracing and test hooks |

The matching version labels do not establish that the Linux and Wii U builds
contain identical code or build options. The research core supplied controlled
traces and CPU checks; the user-facing RetroArch builds supplied gameplay tests.

RetroArch/ProSystem gameplay tests on PC and Wii U established normal play
with the field-goal implementation, good kicks in both directions, a short
kick landing before the posts being called no good, and uninterrupted flight
before the result banner. The label and zero glyph were checked interactively.

Controlled CPU checks of the extra-point helper covered all random bytes for
seven proximity placements in both directions: **3,584 cases**. Close cases
selected the blocked path for 64 of 256 values; far cases selected it for 32.
Tests included ±9 differences and ±10 boundaries, and compared far cases with
the original routine's decision for every byte. Gameplay testing of this
blocking adjustment also produced successful and missed attempts, including
a miss using the fastest direct approach to the kick.

The builder reconstructs the exact playable candidate from the clean original,
checks its SHA-256, and verifies that applying the BPS reconstructs identical
bytes. This proves artifact identity; it does not replace gameplay testing.
Every possible trajectory and emulator has not been tested, and real Atari
7800 hardware compatibility is unverified.

## Reproduce the patch

```sh
python3 tools/build_release.py original.a78 patched.a78 patches/Touchdown-Football-patch.bps
```

Original and patched `.a78` images are both 131,200 bytes. This repository
distributes only the BPS, builder, and documentation. Hashes and application
instructions are in the [README](README.md).
