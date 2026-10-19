# Bench fixtures

`photo-1600.jpg` is the photo `first-load.spec.ts` serves on every card (T-9.10, D-1030):
NASA's official portrait of astronaut Raja Chari, 15 April 2021, by Robert Markowitz, a work of
the United States government and so in the public domain, as Wikimedia Commons records it
(<https://commons.wikimedia.org/wiki/File:Raja_Chari,_official_portrait_(2021).jpg>). The file
Commons serves was checked against the SHA-1 it publishes, `3cfbbc5b7cb32e86bd73dcb03cffad30a193e8ff`,
then put through the API's own `core.images.reencode`, as every approved photo is (D-092): 1,280 ×
1,600, a JPEG at quality 85, 281,135 bytes, SHA-256
`cd07696593a6b53c12e5e52d203b08cd32b72cb9591b16b7a233b3357d91db9d`.

Made by Claude on 19 October 2026 with `make_photo.py` (its docstring says how to run it). The
same original is one of `api/tests/fixtures/faces/`, at 600 pixels there.
