# Real-Time Tree Detection — ROS 2 Pipeline

Connects a camera stream to the tree-detection model through **ROS 2**, using `sensor_msgs/msg/Image` and `cv_bridge`. This README covers the ROS 2 image pipeline only — see [README.md](./ml/README.md) for dataset/training/model details.

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
                                        display / publish
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
    results = model.predict(source=frame)                            # 2. run detection
    annotated_frame = results[0].plot()                              # 3. draw boxes
    cv2.imshow("Tree Detection", annotated_frame)                    # 4. display
    cv2.waitKey(1)
```

The model itself isn't documented here — see the ML README.

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
    └── src/response_stream/
        ├── __init__.py
        └── stream_subs.py
```

`stream_feed` produces images; `response_stream` consumes them and detects. Multiple nodes can subscribe to `/camera/image_raw` at once (e.g. a future recording or navigation node) without changing the publisher.

## Running the System

```bash
cd ~/Documents/mongol_barota/realtime_tree_detection

source /opt/ros/jazzy/setup.bash
source .venv/bin/activate

colcon build
source install/setup.bash

# terminal 1 — camera publisher
ros2 run stream_feed <camera-executable>

# terminal 2 — detection subscriber
ros2 run response_stream stream_subscriber
```

## Debugging Topics

```bash
ros2 topic list                      # /camera/image_raw should appear
ros2 topic type /camera/image_raw    # expect: sensor_msgs/msg/Image
ros2 topic hz /camera/image_raw      # check camera frame rate
```

## Where This Is Headed

This is the first stage of a larger perception pipeline:

```
Camera → ROS 2 Image Topic → Object Detection → Bounding Boxes → Perception → Navigation/Planning → Robot Action
```

ROS 2 is the communication layer connecting these stages; the detection node can later publish its own result topic (e.g. `/tree_detection/image`) or structured detection data for downstream robotics nodes.