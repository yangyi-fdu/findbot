# findbot

Natural-language object search for a simulated mobile robot — *"find the red cup"* →
LLM tool calls → semantic map lookup / active exploration → Nav2 navigation.

**Stack:** ROS 2 Jazzy · Gazebo Harmonic · Nav2 · TurtleBot3 (waffle) · YOLO · LLM tool calling

> Work in progress. See the roadmap below.

## Packages

| Package | Purpose |
|---|---|
| `findbot_bringup` | Launch files and configuration (simulation, navigation, full system) |
| `findbot_behaviors` | Robot behaviors — reactive wanderer (exploration fallback) |

## Quick start

```bash
cd ~/ros2_ws && colcon build --symlink-install && source install/setup.bash
ros2 launch findbot_bringup sim.launch.py            # gui:=true to open the Gazebo GUI
ros2 launch findbot_behaviors wanderer.launch.py     # drive around, avoid obstacles
```

## Roadmap

- [x] Simulation bring-up, reactive obstacle-avoiding node with unit tests
- [ ] SLAM mapping + Nav2 navigation, goals sent from code
- [ ] RGB-D object detection (YOLO) → 3D localization in `map` frame → semantic map
- [ ] `FindObject` action: query memory, otherwise explore until found
- [ ] LLM node: natural language → tool calls → actions
- [ ] Evaluation (success rate, time-to-find), demo video, Docker
