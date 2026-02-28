# Project Assets

## Included

- **`ferry-logo.svg`** — Vector logo (boat silhouette + "Ferry" wordmark). Used in docs and GitHub social preview.

## Required Binary Assets (not tracked in git)

Generate these from the SVG before building releases:

### `ferry.ico` — Windows app icon (used by PyInstaller)

```bash
# Requires ImageMagick
magick ferry-logo.svg -resize 256x256 -background transparent -gravity center -extent 256x256 ferry.ico
```

### `ferry.icns` — macOS app icon (used by PyInstaller)

```bash
mkdir ferry.iconset
for size in 16 32 64 128 256 512; do
  magick ferry-logo.svg -resize ${size}x${size} ferry.iconset/icon_${size}x${size}.png
  magick ferry-logo.svg -resize $((size*2))x$((size*2)) ferry.iconset/icon_${size}x${size}@2x.png
done
iconutil -c icns ferry.iconset
rm -rf ferry.iconset
```

### `ferry-banner.png` — GitHub social preview (1280x640)

```bash
magick ferry-logo.svg -resize 800x400 -background white -gravity center -extent 1280x640 ferry-banner.png
```

Upload via GitHub repo Settings → General → Social preview.
