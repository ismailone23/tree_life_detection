# Tree Detection

YOLO-based detector for **real trees** in images (single class: `0 = tree`).

## Project Structure

```
realtime_tree_detection/
├── models/yolo11n.pt              # pretrained starting weights
├── ml/
│   ├── dataset/
│   │   ├── configs/tree.yaml      # dataset config
│   │   └── tree/{train,valid,test}/{images,labels}/
│   ├── scripts/{train.py, test.py, add_fake.py}
│   └── runs/tree_detector/weights/{best.pt, last.pt}
├── fake/                          # artificial/fake tree images (negatives)
└── requirements.txt
```

## Dataset

- **train** → updates weights. **valid** → picks best checkpoint during training. **test** → final, untouched evaluation.
- YOLO label format, one `.txt` per image, one line per box:
  ```
  class x_center y_center width height   # all normalized 0..1
  0 0.52 0.43 0.31 0.52
  ```
- Empty `.txt` = "no objects here" (used for negatives).

`tree.yaml`:
```yaml
path: /path/to/realtime_tree_detection/ml/dataset/tree
train: train/images
val: valid/images
test: test/images
names:
  0: tree
```

## Training

```python
model = YOLO(str(ROOT / "models/yolo11n.pt"))
model.train(
    data=str(ROOT / "ml/dataset/configs/tree.yaml"),
    epochs=100, imgsz=640, batch=8, device=0, workers=4,
    project=str(ROOT / "ml/runs"), name="tree_detector",
)
```

| Param | Meaning |
|---|---|
| `epochs` | passes over training data — more ≠ always better, watch for overfitting |
| `imgsz` | input resolution; bigger = better small-object detection, more VRAM |
| `batch` | images per step; lower it on CUDA OOM (try 4, then 2) |
| `device` | `0` for GPU, `"cpu"` for CPU |
| `workers` | data-loading processes |
| `pretrained` | fine-tune from `yolo11n.pt` instead of random init |
| `optimizer` | `"auto"` lets Ultralytics pick |
| `lr0` / `lrf` | initial LR / final LR multiplier |
| `momentum`, `weight_decay` | optimization smoothing / regularization |
| `patience` | early-stop if val performance stalls this many epochs |
| `amp` | mixed precision — faster, less memory, needs supported GPU |
| `cache` | cache images in memory for faster repeated loading |

Augmentation knobs: `mosaic`, `mixup`, `fliplr`, `flipud`, `hsv_h/s/v` — help the model generalize to real-world variation.

Outputs land in `ml/runs/tree_detector/`: `best.pt` (use this for inference), `last.pt`, plus `results.csv/png`, `confusion_matrix.png`, `PR_curve.png`, `F1_curve.png`.

## Prediction

```python
model.predict(
    source=str(ROOT / "ml/custom"),   # image, folder, video, or webcam
    imgsz=640, conf=0.25, device=0, save=True,
    project=str(ROOT / "ml/runs/custom_test"), name="predictions",
)
```

`conf` only filters existing predictions — **it doesn't teach the model anything**. A confident false positive (e.g. a fake tree scored 0.91) stays wrong at any threshold; fixing it requires better training data, not a higher `conf`.

## False Positives & Negative Examples

Artificial trees, Christmas trees, fake plants, tree-shaped decor, and posters/photos of trees are **hard negatives** — include them with empty label files so the model learns "looks like a tree ≠ tree."

`add_fake.py` automates this: takes images from `fake/`, renames them, copies into `train/images/`, and creates matching empty `.txt` labels.

## Evaluation

```python
metrics = model.val(
    data=str(ROOT / "ml/dataset/configs/tree.yaml"),
    split="test", imgsz=640, batch=8, device=0,
)
```

- **Precision** — of predicted trees, how many are real? (↑ = fewer false positives)
- **Recall** — of real trees, how many were found? (↑ = fewer misses)
- **mAP50 / mAP50-95** — detection + box-overlap accuracy at IoU 0.50, and averaged over 0.50–0.95 (stricter).

## Workflow

1. Collect real-tree images → 2. Annotate → 3. Add hard negatives → 4. Sanity-check dataset → 5. Train → 6. Check val metrics → 7. Test on unseen images → 8. Find failure cases → 9. Add targeted examples for those failures → 10. Retrain.

**Key rule:** don't add random images to fix a problem — add examples of the specific failure (e.g. model tags bushes as trees → add bush images; misses distant small trees → add more of those).

## Commands

```bash
source .venv/bin/activate
python3 ml/scripts/train.py
python3 ml/scripts/test.py
nvidia-smi          # check GPU
yolo version        # check Ultralytics version
yolo reset settings # for reseting previous project cache
yolo settings
```