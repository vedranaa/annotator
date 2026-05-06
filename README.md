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

When annotating a folder, annotations are saved automatically when navigating between images. Files are written to an `annotations/` folder next to the image folder, named `<stem>_annotated.png`. Images with no annotation are not saved. If you navigate back to an already-annotated image, the existing annotation is reloaded.

## Requirements

- Python 3
- PyQt5
