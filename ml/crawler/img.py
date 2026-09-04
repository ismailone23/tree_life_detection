import argparse
import hashlib
import shutil
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from icrawler.builtin import BingImageCrawler
from PIL import Image, ImageOps, UnidentifiedImageError


EXCLUDE_KEYWORDS = (
    "-illustration -drawing -cartoon -anime -clipart "
    "-painting -sketch -vector -3d -render "
    "-potted -christmas -easter -halloween "
    "-valentine -thanksgiving -birthday -wedding "
    "-furniture -logo -icon -diagram -artificial"
)

NO_TREE_KEYWORDS = "-tree -trees -plant -plants"

TREE_QUERIES = {
    "plant": [
        # Mango
        f'"healthy mango tree" Bangladesh whole tree orchard {EXCLUDE_KEYWORDS}',
        f'"healthy jackfruit tree" Bangladesh whole tree {EXCLUDE_KEYWORDS}',
        f'"healthy coconut tree" Bangladesh whole palm {EXCLUDE_KEYWORDS}',
        f'"healthy betel nut tree" Bangladesh whole palm {EXCLUDE_KEYWORDS}',
        f'"healthy neem tree" Bangladesh whole tree {EXCLUDE_KEYWORDS}',
        f'"healthy mahogany tree" Bangladesh whole tree {EXCLUDE_KEYWORDS}',
        f'"healthy rain tree" Bangladesh full canopy {EXCLUDE_KEYWORDS}',
        f'"healthy banyan tree" Bangladesh whole tree {EXCLUDE_KEYWORDS}',

        f'"healthy roadside tree" Bangladesh whole tree daylight {EXCLUDE_KEYWORDS}',
        
    ],
    "not_plant": [
        # Real camera backgrounds and common tree-like structures. Broad rural
        # landscape searches are avoided because they usually contain trees.
        f"Bangladesh asphalt road close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh city traffic close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh concrete building facade real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh brick wall outdoor real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh corrugated metal wall outdoor photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh bridge concrete structure real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh bus close up outdoor real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh truck close up outdoor real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh rickshaw close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh road sign close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh billboard close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh concrete utility pole close up photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh street light pole real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh cell tower real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh electric transmission tower real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh construction crane outdoor real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh market storefront real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh house exterior real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh boat close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
        f"Bangladesh river water close up real photo {NO_TREE_KEYWORDS} {EXCLUDE_KEYWORDS}",
    ],
}

QUERIES = {
    class_name: [query.strip() for query in queries if query.strip()]
    for class_name, queries in TREE_QUERIES.items()
}

NUM_IMAGES = 40
MIN_IMAGE_SIZE = 224
MAX_ASPECT_RATIO = 4.0
MAX_IMAGE_PIXELS = 40_000_000
NEAR_DUPLICATE_DISTANCE = 4
IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pgm",
    ".png",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}

BING_FILTERS = {
    class_name: {"size": "large", "type": "photo", "license": "creativecommons",}
    for class_name in QUERIES
}

OUTPUT_DIR = Path(__file__).parent.parent / "dataset"


def _load_training_image(
    path: Path,
    min_size: int,
    max_aspect_ratio: float,
) -> tuple[Image.Image | None, str | None]:
    """Decode and validate an image before it enters the dataset."""
    try:
        with Image.open(path) as source:
            width, height = source.size
            if width * height > MAX_IMAGE_PIXELS:
                return None, "too_large"
            if min(width, height) < min_size:
                return None, "too_small"
            if max(width, height) / min(width, height) > max_aspect_ratio:
                return None, "extreme_aspect_ratio"

            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (OSError, UnidentifiedImageError, ValueError, Image.DecompressionBombError):
        return None, "invalid"

    return image, None


def _difference_hash(image: Image.Image) -> int:
    """Return a 64-bit difference hash for visual duplicate detection."""
    grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = grayscale.get_flattened_data()

    return sum(
        1 << (row * 8 + column)
        for row in range(8)
        for column in range(8)
        if pixels[row * 9 + column] < pixels[row * 9 + column + 1]
    )


def image_hash(path: Path) -> int | None:
    """Return an image's perceptual hash, or None when it cannot be decoded."""
    image, _ = _load_training_image(path, min_size=1, max_aspect_ratio=float("inf"))
    if image is None:
        return None

    try:
        return _difference_hash(image)
    finally:
        image.close()


def _pixel_digest(image: Image.Image) -> str:
    digest = hashlib.sha256()
    digest.update(f"{image.width}x{image.height}:RGB".encode("ascii"))
    digest.update(image.tobytes())
    return digest.hexdigest()


def _store_candidate(
    source_path: Path,
    class_dir: Path,
    min_size: int,
    max_aspect_ratio: float,
) -> str:
    image, rejection_reason = _load_training_image(
        source_path,
        min_size=min_size,
        max_aspect_ratio=max_aspect_ratio,
    )
    if image is None:
        return rejection_reason or "invalid"

    try:
        destination = class_dir / f"{_pixel_digest(image)[:24]}.jpg"
        if destination.exists():
            return "exact_duplicate"

        temporary_destination = destination.with_suffix(".jpg.part")
        try:
            image.save(
                temporary_destination,
                format="JPEG",
                quality=95,
                optimize=True,
            )
            temporary_destination.replace(destination)
        finally:
            temporary_destination.unlink(missing_ok=True)
    except (OSError, ValueError):
        return "save_failed"
    finally:
        image.close()

    return "stored"


def remove_near_duplicates(
    output_dir: Path,
    class_names: list[str],
    distance: int = NEAR_DUPLICATE_DISTANCE,
    min_size: int = MIN_IMAGE_SIZE,
    max_aspect_ratio: float = MAX_ASPECT_RATIO,
) -> Counter[str]:
    """Remove invalid and visually duplicated files across all selected classes."""
    known_hashes: list[tuple[int, str]] = []
    stats: Counter[str] = Counter()

    for class_name in class_names:
        class_dir = output_dir / class_name
        image_paths = sorted(
            path
            for path in class_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )

        for image_path in image_paths:
            image, rejection_reason = _load_training_image(
                image_path,
                min_size=min_size,
                max_aspect_ratio=max_aspect_ratio,
            )
            if image is None:
                image_path.unlink()
                stats[rejection_reason or "invalid"] += 1
                continue

            try:
                current_hash = _difference_hash(image)
            finally:
                image.close()

            duplicate_class = next(
                (
                    known_class
                    for known_hash, known_class in known_hashes
                    if (current_hash ^ known_hash).bit_count() <= distance
                ),
                None,
            )
            if duplicate_class is not None:
                image_path.unlink()
                if duplicate_class == class_name:
                    stats["near_duplicate"] += 1
                else:
                    stats["cross_class_duplicate"] += 1
                continue

            known_hashes.append((current_hash, class_name))
            stats["retained"] += 1

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download and clean Google images for a tree image-classification "
            "dataset. Search results still require manual label review."
        )
    )
    parser.add_argument(
        "--num-images",
        type=int,
        default=NUM_IMAGES,
        help="Maximum number of images to download per query.",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        choices=list(QUERIES),
        default=list(QUERIES),
        help="Classes to download (default: all classes).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Dataset output directory.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=MIN_IMAGE_SIZE,
        help="Reject images whose width or height is below this value.",
    )
    parser.add_argument(
        "--max-aspect-ratio",
        type=float,
        default=MAX_ASPECT_RATIO,
        help="Reject images with a width-to-height ratio above this value.",
    )
    parser.add_argument(
        "--duplicate-distance",
        type=int,
        default=NEAR_DUPLICATE_DISTANCE,
        help="Maximum 64-bit perceptual hash distance treated as a duplicate.",
    )
    parser.add_argument(
        "--dedupe-only",
        action="store_true",
        help="Only validate images and remove duplicates; do not download.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Archive selected class directories before downloading.",
    )
    return parser.parse_args()


def archive_existing_images(output_dir: Path, class_name: str) -> Path | None:
    class_dir = output_dir / class_name
    if not class_dir.exists():
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archive_dir = output_dir / "_archive" / timestamp / class_name
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(class_dir), str(archive_dir))
    return archive_dir


def download_images(
    class_name: str,
    output_dir: Path,
    num_images: int,
    min_size: int,
    max_aspect_ratio: float,
) -> Counter[str]:
    class_dir = output_dir / class_name
    class_dir.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()

    for index, query in enumerate(QUERIES[class_name], start=1):
        print(f"[{class_name} {index}/{len(QUERIES[class_name])}] {query}")

        # icrawler starts filenames at 000001 for every crawl. An isolated
        # directory prevents one query from overwriting files from another.
        with tempfile.TemporaryDirectory(
            prefix=f".{class_name}-",
            dir=output_dir,
        ) as temporary_directory:
            crawler = BingImageCrawler(
                storage={"root_dir": temporary_directory},
            )
            try:
                crawler.crawl(
                    keyword=query,
                    max_num=num_images,
                    filters=BING_FILTERS[class_name],
                    file_idx_offset="auto",
                )
            except Exception as error:
                print(f"Warning: query failed: {error}")
                stats["query_failed"] += 1
                continue

            for candidate in sorted(Path(temporary_directory).iterdir()):
                if not candidate.is_file():
                    continue
                result = _store_candidate(
                    candidate,
                    class_dir=class_dir,
                    min_size=min_size,
                    max_aspect_ratio=max_aspect_ratio,
                )
                stats[result] += 1

    return stats


def _format_stats(stats: Counter[str]) -> str:
    return ", ".join(
        f"{name.replace('_', ' ')}: {count}"
        for name, count in sorted(stats.items())
    ) or "no images"


def main() -> None:
    args = parse_args()
    if args.num_images < 1:
        raise SystemExit("--num-images must be at least 1.")
    if args.min_size < 1:
        raise SystemExit("--min-size must be at least 1.")
    if args.max_aspect_ratio < 1:
        raise SystemExit("--max-aspect-ratio must be at least 1.")
    if not 0 <= args.duplicate_distance <= 64:
        raise SystemExit("--duplicate-distance must be between 0 and 64.")
    if args.dedupe_only and args.replace:
        raise SystemExit("--replace cannot be combined with --dedupe-only.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not args.dedupe_only:
        for class_name in args.classes:
            if args.replace:
                archive_dir = archive_existing_images(args.output_dir, class_name)
                if archive_dir is not None:
                    print(f"Archived {class_name} images to {archive_dir}")

            download_stats = download_images(
                class_name,
                output_dir=args.output_dir,
                num_images=args.num_images,
                min_size=args.min_size,
                max_aspect_ratio=args.max_aspect_ratio,
            )
            print(f"Download summary for {class_name}: {_format_stats(download_stats)}")

    # Always compare every available class. This catches a conflicting image
    # even when positive and negative images were downloaded in separate runs.
    available_classes = [
        class_name
        for class_name in QUERIES
        if (args.output_dir / class_name).is_dir()
    ]
    if not available_classes:
        raise SystemExit(f"No class directories found in {args.output_dir}.")

    clean_stats = remove_near_duplicates(
        args.output_dir,
        class_names=available_classes,
        distance=args.duplicate_distance,
        min_size=args.min_size,
        max_aspect_ratio=args.max_aspect_ratio,
    )
    print(f"Cleanup summary: {_format_stats(clean_stats)}")
    print("Manually review labels before creating train/validation/test splits.")


if __name__ == "__main__":
    main()
