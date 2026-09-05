from pathlib import Path

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from ultralytics import YOLO


class StreamSubscriber(Node):
    def __init__(self, node_name: str):
        super().__init__(node_name)

        relative_model_path = Path(
            'ml/runs/tree_detector/weights/best.pt'
        )
        default_model_path = next(
            (
                parent / relative_model_path
                for parent in Path(__file__).resolve().parents
                if (parent / relative_model_path).is_file()
            ),
            '',
        )
        model_path = self.declare_parameter(
            'model_path', str(default_model_path)
        ).value
        if not model_path or not Path(model_path).expanduser().is_file():
            raise FileNotFoundError(
                'YOLO model not found. Set the model_path ROS parameter.'
            )
        self.model = YOLO(str(Path(model_path).expanduser()))

        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        self.get_logger().info('YOLO detection node started')

        self.bridge = CvBridge()

    def image_callback(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            results = self.model.predict(
                source=frame,
                conf=0.6,
                verbose=True
            )
            annotated_frame = results[0].plot()

            cv2.imshow('Received Image', annotated_frame)
            cv2.waitKey(1)
        except Exception as e:
            self.get_logger().error(f'Error converting image: {e}')

    def destroy_node(self):
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    stream_subscriber = StreamSubscriber('stream_subscriber')

    try:
        rclpy.spin(stream_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        stream_subscriber.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
