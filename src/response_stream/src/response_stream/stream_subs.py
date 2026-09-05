import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ultralytics import YOLO
from pathlib import Path
# /home/ismail/Documents/mongol_barota/realtime_tree_detection/ml/runs/tree_detector/weights/best.pt

ROOT = Path(__file__).resolve().parents[3].parent


class StreamSubscriber(Node):
    def __init__(self, node_name: str):
        super().__init__(node_name)
        self.model = YOLO(str(ROOT / "ml/runs/tree_detector/weights/best.pt"))
        self.subscription = self.create_subscription(
            Image,
            "/camera/image_raw",
            self.image_callback,
            10
        )
        self.get_logger().info("YOLO detection node started")

        self.bridge = CvBridge()


    def image_callback(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

            results = self.model.predict(
                source=frame,
                conf=0.6,
                verbose=True
            )
            annotated_frame = results[0].plot()

            cv2.imshow("Received Image", annotated_frame)
            cv2.waitKey(1)
        except Exception as e:
            self.get_logger().error(f"Error converting image: {e}")

    def destroy_node(self):
        cv2.destroyAllWindows()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)

    stream_subscriber = StreamSubscriber("stream_subscriber")

    try:
        rclpy.spin(stream_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        stream_subscriber.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()