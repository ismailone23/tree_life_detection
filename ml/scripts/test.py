from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "runs" / "tree_detector" / "weights" / "best.pt"
TEST_IMAGES = ROOT / "custom"
OUTPUT = ROOT / "runs" / "test_results"

def main():
    model = YOLO(str(MODEL))

    model.predict(
        source=str(TEST_IMAGES),
        imgsz=640,
        conf=0.5,
        device=0,
        save=True,
        project=str(OUTPUT),
        name="predictions"
)

if __name__ == "__main__":
    main()