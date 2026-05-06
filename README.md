# Annotator

A simple interactive image annotator built with PyQt5. Draw colored annotations on top of images using your mouse, and save them as PNG files.

## Usage

**Annotate a folder of images:**
```python
from annotator import annotate_folder
annotate_folder('data')
```

**Annotate a single image file:**
```python
from annotator import annotate_filename
annotate_filename('image.png')
```

**Annotate a numpy array:**
```python
from annotator import annotate_grayscale, annotate_rgba
annotate_grayscale(gray_array)   # 2D uint8 array
annotate_rgba(rgba_array)        # (H, W, 4) uint8 array
```

**From the command line:**
```
python annotator.py image.png
python annotator.py data/
```

## Controls

| Input | Action |
|---|---|
| Mouse drag | Draw annotation |
| `1`–`9` | Select pen label (colour) |
| `0` | Eraser mode |
| `↑` / `↓` | Increase / decrease pen width |
| `←` / `→` | Previous / next image (folder mode) |
| `O` | Cycle overlay mode (both / annotation / image) |
| `Z` (hold) | Enable zoom — drag to select region |
| `Z` (tap) | Reset zoom |
| `S` | Save annotation |
| `H` (hold) | Show help |
| `Q` / `Esc` | Close |

## Folder mode

`annotate_folder(foldername, annotations_directory=None)` loads all supported images in `foldername` (extensions: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`) in sorted order.

Annotations are saved in `annotations/` folder next to the image folder, or in `annotations_directory` if provided. When you move between images (`←` / `→`) or close the window, the current annotation is saved, and will be reloaded if you return to the same image later.

## Requirements

- Python 3
- PyQt5
