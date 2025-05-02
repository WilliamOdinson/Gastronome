## PNG Icon Generation

Use the PIL to create `.png` simple favicon images in multiple sizes.

```python
from PIL import Image, ImageDraw, ImageFont

# CONSTANTS
TEXT = "G"
FONT_PATH = "YourFont.ttf"
OUTPUT_FOLDER = "./"
SIZE_TO_FONT_SIZE = {
    (16, 16): 10,
    (57, 57): 32,
    (64, 64): 40,
    (72, 72): 40,
    (114, 114): 72,
    (144, 144): 90,
}

for (img_width, img_height), font_size in SIZE_TO_FONT_SIZE.items():
    font = ImageFont.truetype(FONT_PATH, font_size)

    bbox = font.getbbox(TEXT)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    image = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    x = (img_width - text_width) // 2 - bbox[0]
    y = (img_height - text_height) // 2 - bbox[1]

    draw.text((x, y), TEXT, font=font, fill="black")

    output_path = f"{OUTPUT_FOLDER}favicon_{img_width}x{img_height}.png"
    image.save(output_path)
    print(f"Saved {output_path}")
```

## SVG Icon Generation

Use the `svgwrite` library to generate an `.svg` version of the favicon, ensuring that font usage is system-compatible.

```python
import svgwrite

TEXT = "G"
# The Font must be installed in the system fonts
FONT_FAMILY = "YourFont"
FONT_SIZE = 24
SVG_FILENAME = "favicon.svg"
SVG_SIZE = ("165px", "35px")
TEXT_INSERT = ("0px", "26px")
TEXT_COLOR = "black"

dwg = svgwrite.Drawing(SVG_FILENAME, size=SVG_SIZE)

dwg.add(
    dwg.text(
        TEXT,
        insert=TEXT_INSERT,
        fill=TEXT_COLOR,
        font_family=FONT_FAMILY,
        font_size=f"{FONT_SIZE}px"
    )
)

dwg.save()
print(f"Saved {SVG_FILENAME}")
```