# Nhận diện biểu cảm khuôn mặt và điều khiển TurtleBot

Package ROS 2 Humble, Ubuntu 22.04/Python 3.10: **DeepFace + OpenCV** nhận diện
webcam, hiển thị video, khung mặt, nhãn, độ tin cậy và lệnh vận tốc theo thời gian thực.
Lệnh `geometry_msgs/msg/Twist` được phát ở **20 Hz** lên `/cmd_vel`.

| Biểu cảm | Hành động | `linear.x` (m/s) | `angular.z` (rad/s) |
|---|---|---:|---:|
| Happy | Đi theo cung trái | 0.10 | +0.35 |
| Sad | Đi theo cung phải | 0.10 | -0.35 |
| Neutral | Dừng ngay | 0 | 0 |
| Angry | Lùi nhẹ 1.5 s, khoảng 0.12 m | -0.08 | 0 |
| Surprise | Xoay trái một vòng, đo bằng `/odom` | 0 | +0.60 |
| Fear | Tiến nhẹ 1.5 s, khoảng 0.15 m | +0.10 | 0 |

Happy/Sad chạy khi tiếp tục nhận diện được biểu cảm. Angry/Fear/Surprise chỉ chạy
**một lần** khi giữ nguyên biểu cảm; đổi sang Neutral hoặc một biểu cảm hợp lệ khác
rồi trở lại để chạy lần tiếp theo. Hướng trái/phải theo hệ tọa độ robot.

## 1. Cài đặt và build trong Ubuntu/WSL

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
# Nếu chưa có venv: sudo apt install python3-venv
bash src/turtlebot4_emotion_control/tools/install_vision.sh
colcon build --symlink-install --packages-select turtlebot4_emotion_control
source install/setup.bash
```

Script tạo `.venv-emotion` riêng với `--system-site-packages`, cài các phiên bản
trong `requirements-vision.txt` và tải trước trọng số Emotion về `~/.deepface/weights`.
Cần Internet ở lần cài đầu tiên; TensorFlow có dung lượng lớn. Build bằng Python ROS
mặc định; `run.sh` bổ sung thư viện venv cho executable ROS khi chạy.
Model có thể nạp chậm trên WSL; robot đứng yên trong lúc cửa sổ báo đang nạp model.

## 2. Bật robot hoặc mô phỏng

Khởi động bringup TurtleBot như bình thường và xác nhận topic:

```bash
ros2 topic info /cmd_vel -v
ros2 topic echo /odom --once
```

`/cmd_vel` cần subscriber nhận `geometry_msgs/msg/Twist`. `/odom` cần
`nav_msgs/msg/Odometry` cho Surprise. Không có odometry mới thì robot không xoay.
Nếu odometry xuất hiện sau khi đã giữ Surprise, đổi sang Neutral rồi Surprise lại.
Robot và node phải dùng cùng `ROS_DOMAIN_ID` và cấu hình DDS.

Workspace này đã có mô phỏng TurtleBot 4 trong sân trống; có thể chạy ở terminal riêng:

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch turtlebot4_gesture_control gesture_sim.launch.py gui:=true
```

Launch trên chỉ bật mô phỏng, không bật node nhận diện cử chỉ. Chờ controller active
trước khi thử. Đóng teleop, Nav2 và các node điều khiển khác để chỉ có một nguồn `/cmd_vel`.

## 3. Chạy webcam gắn trực tiếp vào Ubuntu

```bash
cd ~/ros2_ws
bash src/turtlebot4_emotion_control/tools/run.sh camera_source:=0
```

Thử `camera_source:=1` nếu webcam ở index khác. `Q`, `Esc`, đóng cửa sổ hoặc `Ctrl+C`
sẽ dừng robot và thoát. Không cần bấm phím để chọn hành động.

## 4. Webcam Windows khi dùng WSL

Webcam Windows thường chưa xuất hiện ở `/dev/video*` trong WSL. Dùng cầu webcam
có sẵn trong workspace, ghi ảnh JPEG kèm timestamp/sequence vào file dùng chung.

Trong **PowerShell Windows**, dùng Python Windows đã cài OpenCV:

```powershell
# Máy này có Python Windows tại đường dẫn dưới; nếu cần: python -m pip install opencv-python
& 'C:\Users\khoa8\miniconda3\python.exe' '\\wsl.localhost\Ubuntu-22.04\home\khoa\ros2_ws\src\turtlebot4_gesture_control\tools\windows_camera_bridge.py' --output 'C:\Users\khoa8\Downloads\turtlebot4_emotion_runtime\camera.frame'
```

Trong **Ubuntu/WSL**:

```bash
cd ~/ros2_ws
bash src/turtlebot4_emotion_control/tools/run.sh \
  camera_source:=file:///mnt/c/Users/khoa8/Downloads/turtlebot4_emotion_runtime/camera.frame
```

Không cần mở cổng mạng. Đóng ứng dụng khác đang chiếm webcam nếu camera không mở được.
Ảnh cũ quá 0.35 s hoặc sequence lặp không được dùng làm một ảnh mới.

## Tham số và quan sát

Các vận tốc, thời gian, ngưỡng tin cậy nằm trong `config/emotion_control.yaml`.
Sửa YAML rồi khởi động lại. Các đối số launch:

```bash
bash src/turtlebot4_emotion_control/tools/run.sh \
  camera_source:=0 show_window:=false cmd_vel_topic:=/cmd_vel odom_topic:=/odom
# Hoặc: config:=/duong/dan/emotion_control.yaml
```

`show_window:=false` dùng cho máy không có giao diện. Xem kết quả tại:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 topic echo /emotion_control/status
```

Status JSON chứa `emotion`, `confidence`, `result_age`, `action`, `state`, vận tốc
và thông tin lỗi. Chỉ suy luận thuộc tính `emotion`, không nhận dạng danh tính.
Mô hình và API tham khảo: [DeepFace v0.0.93](https://github.com/serengil/deepface/tree/v0.0.93).

## Xử lý nhiễu và giới hạn

- Cần ít nhất 3 kết quả mới liên tiếp, kéo dài ít nhất 0.35 s, độ tin cậy từ 60%
  trước khi bắt đầu một hành động. Neutral dừng ngay khi vượt ngưỡng tin cậy.
- Không có mặt, nhiều mặt, nhãn Disgust hoặc độ tin cậy thấp đều dừng; không ép
  nhãn ngoài yêu cầu thành một trong 6 lệnh.
- Camera và AI chạy ở hai worker, chỉ giữ ảnh/kết quả mới nhất. Timer ROS không
  chờ inference. Camera cũ quá 0.4 s, kết quả cũ quá 1.5 s, lỗi model hoặc timer
  trễ quá 0.3 s đều phát vận tốc 0. Nếu CPU chậm hơn ngưỡng, robot sẽ dừng;
  xem `result_age` trước khi điều chỉnh cấu hình.
- Ảnh suy luận được thu nhỏ về chiều rộng tối đa 320 px để giảm tải CPU;
  video hiển thị và tọa độ khung mặt vẫn dùng kích thước ảnh gốc.
- Surprise cộng dồn chênh lệch yaw qua biên ±π; dừng sau khoảng 2π rad với sai số
  0.03 rad và độ trễ điều khiển. Odometry cũ quá 0.5 s sẽ dừng vòng xoay.
- Tiến/lùi dùng thời gian thực; quãng đường là ước lượng. Cung trái/phải có bán
  kính lý tưởng khoảng 0.286 m. Không có chức năng tránh vật cản.
- Giữ mặt trong khung hình trong suốt hành động. Thử trong vùng trống và dùng
  watchdog của driver robot (`cmd_vel_timeout`, ví dụ 0.5 s) vì mất nguồn/kill -9
  không thể gửi lệnh dừng. Node gửi lệnh 0 trước khi thoát bình thường.

## Kiểm tra

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
PYTHONPATH="$PWD/src/turtlebot4_emotion_control:$PYTHONPATH" \
  /usr/bin/python3 -m pytest src/turtlebot4_emotion_control/test -v
colcon test --packages-select turtlebot4_emotion_control --event-handlers console_direct+
colcon test-result --test-result-base build/turtlebot4_emotion_control
```

Unit test dùng dữ liệu giả để kiểm tra hành vi/dừng, không đo độ chính xác model.
Kiểm tra nhận diện thực tế cần webcam, ánh sáng tốt và từng biểu cảm của người demo.
