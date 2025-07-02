# offboard_signal.py
import time
import multiprocessing
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, VehicleCommand


def _signal_loop(drone_id: int, publish_interval: float, count_interval: float, stop_event: multiprocessing.Event):
    rclpy.init()
    node = rclpy.create_node(f"offb_signal_{drone_id}")
    offboard_pub = node.create_publisher(OffboardControlMode, f"/px4_{drone_id}/fmu/in/offboard_control_mode", 10)
    command_pub  = node.create_publisher(VehicleCommand,      f"/px4_{drone_id}/fmu/in/vehicle_command",        10)

    armed = offboard = False
    count = 0
    last_count_ts = time.time()

    try:
        while not stop_event.is_set():
            now = time.time()
            # always publish at publish_interval
            t = node.get_clock().now().nanoseconds
            publish_offboard(offboard_pub, t)

            # only increment “count” every count_interval seconds
            if now - last_count_ts >= count_interval:
                count += 1
                last_count_ts = now

                if count == 31 and not armed:
                    send_arm(command_pub, drone_id, t)
                    armed = True
                if count == 36 and not offboard:
                    send_offboard_mode(command_pub, drone_id, t)
                    offboard = True
                    print(f"Drone {drone_id} is ready")

                # if count % 20 == 0:
                #     node.get_logger().info(f"{t} Offboard 20 pings for drone {drone_id}")

            time.sleep(publish_interval)
    finally:
        node.destroy_node()
        rclpy.shutdown()

def publish_offboard(offboard_pub, t):
    offboard = OffboardControlMode()
    offboard.timestamp = t
    offboard.position = True
    offboard_pub.publish(offboard)

def send_arm(arm_pub, drone_id,t):
    msg = VehicleCommand()
    msg.timestamp = t
    msg.param1 = 1.0
    msg.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
    msg.target_system = int(drone_id) + 1
    msg.target_component = 1
    msg.source_system = 1
    msg.source_component = 1
    msg.from_external = True
    arm_pub.publish(msg)

def send_offboard_mode(offboard_pub, drone_id, t):
    msg = VehicleCommand()
    msg.timestamp = t
    msg.param1 = 1.0
    msg.param2 = 6.0
    msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
    msg.target_system = int(drone_id) + 1
    msg.target_component = 1
    msg.source_system = 1
    msg.source_component = 1
    msg.from_external = True
    offboard_pub.publish(msg)

class OffboardSignal:
    def __init__(self, drone_id, interval):
        try:
            multiprocessing.set_start_method('spawn', force=True)
            self.drone_id = drone_id
            self.interval = interval
            self._stop = multiprocessing.Event()
            self._proc = None
        except Exception as e:
            print(f"❗ Error initializing OffboardSignal: {e}")

    def start(self):
        try:
            if self._proc and self._proc.is_alive():
                return
            self._stop.clear()
            self._proc = multiprocessing.Process(
                target=_signal_loop,
                args=(self.drone_id, self.interval, 0.6333,self._stop),
            )
            self._proc.start()
        except Exception as e:
            print(f"❗ Error starting OffboardSignal: {e}")

    def stop(self):
        if not self._proc:
            return
        self._stop.set()
        self._proc.join()
        self._proc = None

