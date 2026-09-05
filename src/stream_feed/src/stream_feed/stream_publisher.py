import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

class CameraPublisher(Node):
    def __init__(self, node_name: str):
        super().__init__(node_name)
        self.publisher_ = self.create_publisher(Image, "/camera/image_raw", 10)
        self.bridge = CvBridge()

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: Could not open video stream.")

        self.timer = self.create_timer(
            1.0 / 30.0,
            self.publish_frame
        )

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            return

        msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        self.publisher_.publish(msg)
        self.get_logger().info("Published frame")

    def destroy_node(self):

        self.cap.release()

        cv2.destroyAllWindows()
        
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)

    camera_publisher = CameraPublisher("camera_publisher")

    try:
        rclpy.spin(camera_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        camera_publisher.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
