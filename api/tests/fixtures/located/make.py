"""Writes the three located photos the D-092 tests read: `located.jpg`,
`located.png`, `located.webp`. Run once, from `api/`:
`uv run python -m tests.fixtures.located.make`.

Made by Claude on 4 October 2026 with Pillow 12.3.0. The files are committed,
not made at test time, so the copies an independent reader confirmed are the
copies the tests use; T-4.4 records which readers confirmed the location.

Every place a location can hide in each format carries one, each with a marker
the tests look for in the bytes:
- EXIF's GPS block: 12°58'17.76" N, 77°35'40.56" E (central Bengaluru, a
  public street, nobody's home), altitude 920 m, and a camera Make;
- XMP, with the same coordinates written as text;
- JPEG: an ICC profile, a comment segment, and bytes after the image's end;
- PNG: a text chunk, and bytes after IEND.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ExifTags, Image, ImageCms, ImageDraw, PngImagePlugin

HERE = Path(__file__).resolve().parent
# What the tests look for: each must be in the photo and never in the output.
MAKE = "VELORA-CAMERA-MAKE"
LATITUDE = (12.0, 58.0, 17.76)
LONGITUDE = (77.0, 35.0, 40.56)
COORDINATES = "12.971600,77.594600"
XMP_MARK = "VELORA-XMP-LOCATION"
COMMENT_MARK = "VELORA-COMMENT-LOCATION"
TEXT_MARK = "VELORA-PNG-TEXT-LOCATION"
TRAILER_MARK = "VELORA-TRAILER-LOCATION"
ORIENTATION = 6  # stored on its side: turned 90° clockwise when shown


def exif() -> bytes:
    data = Image.Exif()
    data[ExifTags.Base.Make] = MAKE
    data[ExifTags.Base.Orientation] = ORIENTATION
    data[ExifTags.IFD.GPSInfo] = {
        ExifTags.GPS.GPSLatitudeRef: "N",
        ExifTags.GPS.GPSLatitude: LATITUDE,
        ExifTags.GPS.GPSLongitudeRef: "E",
        ExifTags.GPS.GPSLongitude: LONGITUDE,
        ExifTags.GPS.GPSAltitudeRef: b"\x00",
        ExifTags.GPS.GPSAltitude: 920.0,
    }
    return data.tobytes()


def xmp() -> bytes:
    return (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:exif="http://ns.adobe.com/exif/1.0/" '
        f'xmlns:velora="https://example.invalid/velora/" velora:mark="{XMP_MARK}" '
        'exif:GPSLatitude="12,58.296N" exif:GPSLongitude="77,35.676E"/>'
        "</rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode()


def picture() -> Image.Image:
    """Stored on its side (Orientation 6): a red band along the left edge,
    which is the top once turned upright."""
    image = Image.new("RGB", (480, 360), (40, 90, 160))
    ImageDraw.Draw(image).rectangle((0, 0, 59, 359), fill=(220, 30, 30))
    return image


def main() -> None:
    image = picture()
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    jpeg = HERE / "located.jpg"
    image.save(jpeg, "JPEG", quality=90, exif=exif(), xmp=xmp(), icc_profile=icc)
    # A comment segment (COM, 0xFFFE) right after SOI, then bytes after EOI.
    body = jpeg.read_bytes()
    comment = f"{COMMENT_MARK} {COORDINATES}".encode()
    com = b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment
    trailer = f"{TRAILER_MARK} {COORDINATES}".encode()
    jpeg.write_bytes(body[:2] + com + body[2:] + trailer)

    png = HERE / "located.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("Location", f"{TEXT_MARK} {COORDINATES}")
    text.add_itxt("XML:com.adobe.xmp", xmp().decode())
    image.save(png, "PNG", exif=exif(), pnginfo=text)
    png.write_bytes(png.read_bytes() + trailer)

    image.save(HERE / "located.webp", "WEBP", quality=90, exif=exif(), xmp=xmp())


if __name__ == "__main__":
    main()
