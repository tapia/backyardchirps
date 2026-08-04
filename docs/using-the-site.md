# Using the site

## The pages

**Recent** is the home page: everything heard in the last 24 hours, newest first. Each entry
gives a species, the time it was heard, a confidence score, and a play button for the actual
recording.

**All Species** is the catalogue of everything ever detected here, sortable by how often a
bird turns up, by how recently, or alphabetically. The search box covers the whole BirdNET
taxonomy, so you can look up a species that has never been detected and see that it hasn't.

**A species page** opens on a photo, a range map, and a few headline facts: whether it is a
common or occasional visitor, what time of day it is most active, how many days running it
has been heard. Three tabs sit underneath.

| Tab | Shows |
|---|---|
| Info | A seasonality chart from eBird, not from your recordings. Useful for checking a surprising detection. |
| Detections | Your own history, as a timeline and an activity-by-hour chart |
| Recordings | Every saved clip, sortable by date or confidence |

## Confidence scores

Every detection carries a number from 0 to 100%. It is how sure BirdNET is, not the chance
that the bird was really there. A 60% detection is not "wrong 40% of the time": it means the
model found the sound somewhat similar to its training examples.

Treat them in bands:

| Score | What it usually means |
|---|---|
| Above 90% | Almost always right. A clear, close, uninterrupted call. |
| 70% to 90% | Usually right. Published without human review. |
| 40% to 70% | Worth a listen. Goes to the review queue. |
| Below 40% | Never recorded at all. |

The **Min confidence** filter in the navbar (Low / Medium / High) sets the floor for what the
pages show. It starts at High, so the site is cautious until you tell it otherwise. Drop it
to Low to see everything, including detections still waiting for review.

## Reviewing recordings

Detections the system isn't confident about land in **Pending Review**, and anyone can work
through them. This is the one part of the site where you are not just reading.

Open a pending recording and you get the clip, a spectrogram, and reference calls for the
species BirdNET guessed. Listen to both, then:

- **Save** if the identification looks right.
- **Reassign species** if it was something else. The picker is limited to species known to
  occur here.
- **Delete** if it was a car, a dog, or nothing at all. This erases the recording permanently.
- **Skip** to leave it for later.

Confirming sets the confidence to 100%, because a person has now checked it and BirdNET's
guess no longer tells you anything. That original guess is kept rather than thrown away.

You can also revisit a recording that was never pending. Every row in a species' Recordings
tab has an edit control, so an auto-confirmed detection can be reassigned or deleted later.

### When two birds share one recording

Each bird in a clip is identified separately, so the clear one may be confirmed automatically
while the faint one waits for review. The dialog then lists **Species identified in this
recording**, marks the one you are looking at, and names it on the delete button. Removing one
identification never looks like removing the whole recording.

You cannot reassign to a species the recording already holds. It stays in the search results,
greyed out and marked **Already identified in this recording**. If you decide the bird you are
reviewing was really that other one, delete this identification instead: the other is already
there, and the recording ends up with one of each bird rather than two of the same.

Reassigning to a species identified in a *different* recording is fine. Those are two separate
sightings.

### Clearing several at once

When the queue fills with obvious noise, tick the checkbox on each row. In the **Species**
view, the checkbox on a group header takes the whole group at once. A bar then appears at the
bottom with **Confirm** and **Delete** for everything you selected. Confirming this way keeps
each recording's species as BirdNET had it. Deleting erases them permanently, so it asks
first.

## What a recording page shows

The clip and its spectrogram, and below them how it was identified:

- **Whether a person reviewed it.** If the reviewer changed the species, BirdNET's original
  guess and its confidence are shown too.
- **How long BirdNET took**, in milliseconds. A clip arrives every 1.5 seconds, so on a
  Raspberry Pi a time approaching 1500 ms means the station is close to falling behind.
- **Everything BirdNET heard**, down to a 5% floor, highest first. That includes weak guesses
  that never became detections, blacklisted species, and non-bird sounds, but only species
  that can occur at the station, since the location filter runs first. Older recordings show
  none of this.

## Language

English and Spanish, switchable from the navbar. It changes the interface and the common names
of birds; scientific names stay as they are.

---

## How detections actually happen

Everything above is what you see. This is what produces it.

### Listening in overlapping windows

BirdNET only accepts 3-second clips, so the recorder keeps a rolling 3-second buffer and takes
a snapshot every 1.5 seconds. Consecutive clips overlap by half:

```
clip 1:  [===== 3s =====]
clip 2:         [===== 3s =====]
clip 3:                [===== 3s =====]
         └────────────────────────────▶ time
```

Without the overlap, a call that crossed from one clip into the next would be cut into two
pieces, each too short to identify, and missed twice. With it, every moment of audio sits
complete inside at least one clip.

### Deciding what to believe

Each clip goes to BirdNET with the station's coordinates and the date, which lets the model
rule out species that don't occur here or aren't around this time of year. It returns
everything it hears above 40% confidence.

Those are candidates, not detections. BirdNET can also name insects, mammals, amphibians and
reptiles, and this is a bird station, so non-birds are dropped before they can reach the
review queue. What is left is accepted only if either:

- it appears in **at least 2 of the last 3 clips**, or
- it scores **80% or higher** in any single clip.

The second rule exists for short, distinctive calls. A House Sparrow chirp can be over before
the next clip starts, so requiring repetition would throw away detections BirdNET is nearly
certain about.

A detection accepted by repetition keeps all the clips it appeared in, joined into one
recording of up to 6 seconds, which gives a reviewer more to work with. One accepted by the
80% rule keeps only its own clip, so no unrelated audio is mixed in.

### Storing it

A bird singing for ten minutes would otherwise produce hundreds of records, so detections of
the same species are grouped into 3-minute blocks, keeping only the most confident one. The
time shown against a detection is when its audio was captured, to the second.

From there it depends on the score. At or above 70% the detection is published directly.
Below that it waits in the review queue. Either way the recording is saved.

```
BirdNET candidates
     │
     ├─ blacklisted species, non-birds ────▶ discarded
     │
     ▼
2-of-3 clips, or one clip ≥ 80%?
     │
     ├─ no ───────────────────────────────▶ discarded
     │
     ▼ yes
stitch clips, keep best per 3-minute block
     │
     ├─ confidence ≥ 70% ─────────────────▶ shown on the site
     └─ confidence < 70% ─────────────────▶ pending review
```

Those thresholds are the defaults. An admin can change them, globally or for one species: see
the [admin guide](admin-guide.md).
