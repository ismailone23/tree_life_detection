# Real-Time Tree Detection — ROS 2 Pipeline

Connects a camera stream to the tree-detection model through **ROS 2**, using `sensor_msgs/msg/Image` and `cv_bridge`. This README covers the ROS 2 image pipeline only — see the [ML README](./ml/README.md) for dataset, training, and model details.

## Architecture

```
Camera Node                          Detection Node
  physical camera                      subscribe /camera/image_raw
       ↓                                      ↓
   OpenCV frame                        CvBridge → OpenCV frame
       ↓                                      ↓
  cv2_to_imgmsg()                       model.predict(frame)
       ↓                                      ↓
sensor_msgs/msg/Image  ──topic──►      results[0].plot() → annotated frame
  /camera/image_raw                            ↓
                                           display
```

Camera and detection are separate nodes connected only by the `/camera/image_raw` topic — the camera doesn't know about the model, and either side can be swapped or extended (recording, visualization, navigation nodes, etc.) without touching the other.

## CvBridge: ROS ↔ OpenCV

ROS 2 transports images as `sensor_msgs/msg/Image` messages, not raw NumPy arrays. `CvBridge` converts between the two:

**Publishing (camera node):**
```python
self.publisher_ = self.create_publisher(Image, "/camera/image_raw", 10)

ret, frame = self.cap.read()                       # OpenCV frame (numpy array)
msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
self.publisher_.publish(msg)
```

**Subscribing (detection node):**
```python
self.subscription = self.create_subscription(
    Image, "/camera/image_raw", self.image_callback, 10
)

def image_callback(self, msg):
    frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
```

`bgr8` is used because OpenCV represents color images in BGR (not RGB) channel order — keep this consistent on both `cv2_to_imgmsg` and `imgmsg_to_cv2`.

## Detection Node Callback

```python
def image_callback(self, msg):
    frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")   # 1. ROS → OpenCV
    results = self.model.predict(                                   # 2. run detection
        source=frame, conf=0.6, verbose=True
    )
    annotated_frame = results[0].plot()                              # 3. draw boxes
    cv2.imshow("Received Image", annotated_frame)                    # 4. display
    cv2.waitKey(1)
```

The detection node currently displays the annotated image locally. It does not publish annotated images or structured detections yet. The model itself is documented in the [ML README](./ml/README.md).

## Package Structure

```
src/
├── stream_feed/            # publishes camera images
│   ├── package.xml, setup.py, setup.cfg, resource/
│   └── src/stream_feed/
│       ├── __init__.py
│       └── stream_publisher.py
│
└── response_stream/        # subscribes + runs detection
    ├── package.xml, setup.py, setup.cfg, resource/
    ├── stream_subscriber   # launcher that uses the active virtualenv
    └── src/response_stream/
        ├── __init__.py
        └── stream_subs.py
```

`stream_feed` produces images; `response_stream` consumes them and detects. Multiple nodes can subscribe to `/camera/image_raw` at once (e.g. a future recording or navigation node) without changing the publisher.

## Setup

The Python virtual environment must include the ROS system packages, because `rclpy` and `cv_bridge` are installed by ROS rather than pip. From the workspace root:

```bash
cd ~/Documents/mongol_barota/realtime_tree_detection

source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y

python3 -m venv --system-site-packages .venv
touch .venv/COLCON_IGNORE
source .venv/bin/activate
python -m pip install -r requirements.txt

colcon build
source install/setup.bash
```

The trained checkpoint is expected at:

```text
ml/runs/tree_detector/weights/best.pt
```

Files under `runs/` and `weights/` are ignored by Git, so a fresh clone will not contain this checkpoint. Train the model, copy/download `best.pt`, or provide another checkpoint with the `model_path` ROS parameter:

```bash
ros2 run response_stream stream_subscriber \
  --ros-args -p model_path:=/absolute/path/to/best.pt
```

## Running the System

In every new terminal, load ROS, activate the virtual environment, and source the workspace:

```bash
cd ~/Documents/mongol_barota/realtime_tree_detection
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
source install/setup.bash
```

Start the nodes in separate terminals:

```bash
# terminal 1 — camera publisher (camera index 0, target rate 30 Hz)
ros2 run stream_feed stream_publisher

# terminal 2 — detection subscriber
ros2 run response_stream stream_subscriber
```

The subscriber launcher uses `$VIRTUAL_ENV/bin/python` when the environment is active. This is required because Ultralytics and PyTorch are installed inside `.venv`, while ROS command-line tools may use `/usr/bin/python3`.

## Debugging Topics

```bash
ros2 topic list                      # /camera/image_raw should appear
ros2 topic type /camera/image_raw    # expect: sensor_msgs/msg/Image
ros2 topic hz /camera/image_raw      # check camera frame rate
```

A topic can appear in `ros2 topic list` even when no frames are arriving. Use `ros2 topic hz /camera/image_raw` to confirm that the publisher is producing images.

## Troubleshooting

### `ModuleNotFoundError: No module named 'ultralytics'`

**Cause:** the generated ROS executable used `/usr/bin/python3`, but Ultralytics was installed only in `.venv`. Activating a virtual environment does not change an interpreter path already embedded in a generated executable.

**Fix:** `response_stream` now installs `src/response_stream/stream_subscriber`, a shell launcher that explicitly runs the module with the active virtualenv. Activate the environment, verify the dependency, rebuild the package, and source the new installation:

```bash
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -c "import ultralytics; print(ultralytics.__version__)"

colcon build --packages-select response_stream
source install/setup.bash
ros2 run response_stream stream_subscriber
```

The launcher is registered by `src/response_stream/setup.py` through `scripts=['stream_subscriber']`. Do not replace it with a generated `console_scripts` entry unless the package is always built using the virtualenv interpreter.

### `FileNotFoundError: YOLO model not found`

**Cause:** Ultralytics loaded successfully, but the node could not find a checkpoint. The old code also derived the path from the installed Python file, which incorrectly produced `install/response_stream/ml/...` after a copy-install build.

**Fix:** the node now searches parent directories for `ml/runs/tree_detector/weights/best.pt`. Verify that the file exists:

```bash
ls -lh ml/runs/tree_detector/weights/best.pt
```

If the checkpoint is elsewhere, pass an absolute path:

```bash
ros2 run response_stream stream_subscriber \
  --ros-args -p model_path:=/absolute/path/to/best.pt
```

### Camera topic exists but no frames arrive

The publisher currently opens camera index `0`. Check that the camera is available and that another process is not using it:

```bash
ros2 topic hz /camera/image_raw
```

### No detection window appears

The subscriber uses `cv2.imshow`, so it requires a graphical desktop session. It will not display a window in a headless environment unless GUI forwarding or a virtual display is configured.

## Where This Is Headed

This is the first stage of a larger perception pipeline:

```
Camera → ROS 2 Image Topic → Object Detection → Bounding Boxes → Perception → Navigation/Planning → Robot Action
```

ROS 2 is the communication layer connecting these stages; the detection node can later publish its own result topic (e.g. `/tree_detection/image`) or structured detection data for downstream robotics nodes.
