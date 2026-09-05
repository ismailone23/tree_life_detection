from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]



def main():
    model = YOLO(str(ROOT / "models" / "yolo11n.pt"))

    model.train(
        data=str(ROOT / "ml/dataset/configs/tree.yaml"),
        epochs=100,
        imgsz=640,
        batch=8,
        device=0,
        workers=4,
        project=str(ROOT / "ml/runs"),
        name="tree_detector",
    )


if __name__ == "__main__":
    main()