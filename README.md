# Backyard Chirps

A self-hosted bird listening station. Point a microphone wherever birds are, and get a
searchable record of everything heard there.

Audio is captured continuously and identified as it arrives by
[BirdNET](https://github.com/kahst/BirdNET-Analyzer). Every detection keeps its recording, so
what you end up with is an archive you can listen to rather than a list of names: which birds
visit, at what times of day, and how that changes across the year.

It runs unattended on a Raspberry Pi and publishes its own website, in English or Spanish.

## How it works

```
Microphone  →  BirdNET  →  filters  →  database  →  website
              (what bird     (is it     (one record   (browse and
               is this?)     really      per species   listen)
                             there?)     per 3 min)
```

BirdNET returns a guess and a confidence score for every 3-second clip. The filters in the
middle are what make the difference: a false alarm appears once and is gone, while a real bird
keeps calling. Anything the system is still unsure about waits for a person to confirm it.

[How detections actually happen](docs/using-the-site.md#how-detections-actually-happen) has the
rules in full.

## Documentation

| Guide | For |
|---|---|
| [Using the site](docs/using-the-site.md) | Visitors: browsing, confidence scores, reviewing recordings |
| [Admin guide](docs/admin-guide.md) | Running a station: settings, per-species rules, monitoring |
| [Installation](docs/installation.md) | Setting up a Raspberry Pi, and how deploys work afterwards |
| [Architecture](docs/devel/architecture.md) | Developers: local setup, how it runs, how the code is laid out |
| [Frontend](docs/devel/frontend.md) | Developers: the Vue app |

## Contributing

Bug reports and pull requests are welcome through the repository's issue tracker.
[Architecture](docs/devel/architecture.md) covers local setup, the way the backend is organised
and how to run the tests. [Frontend](docs/devel/frontend.md) covers the Vue app.

## Licence

AGPL-3.0. See [LICENSE](LICENSE).

BirdNET's models are licensed CC BY-NC-SA 4.0, which is **non-commercial**, so no build of
this project as a whole may be put to commercial use whatever the code licence says.
[NOTICE](NOTICE) credits every third party involved and records their terms.
