from pathlib import Path
import shutil

# Project root
ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "fake"
TRAIN_IMAGES = ROOT / "dataset/tree/train/images"
TRAIN_LABELS = ROOT / "dataset/tree/train/labels"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    TRAIN_IMAGES.mkdir(parents=True, exist_ok=True)
    TRAIN_LABELS.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in SOURCE.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not images:
        print(f"No images found in: {SOURCE}")
        return

    print(f"Found {len(images)} fake/non-tree images.")

    for index, image in enumerate(images, start=1):
        # Keep original extension
        new_name = f"fake_{index:04d}{image.suffix.lower()}"

        destination_image = TRAIN_IMAGES / new_name
        destination_label = TRAIN_LABELS / f"fake_{index:04d}.txt"

        # Copy image
        shutil.copy2(image, destination_image)

        # Create empty label file
        destination_label.touch()

        print(f"Added: {new_name}")

    print("\nDone!")
    print(f"Images: {TRAIN_IMAGES}")
    print(f"Labels: {TRAIN_LABELS}")


if __name__ == "__main__":
    main()