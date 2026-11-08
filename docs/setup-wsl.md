# Running findbot on Windows with WSL2

findbot was developed on a laptop (Ryzen 7 5700U, integrated AMD graphics, 16 GB RAM) in
WSL2 with Ubuntu 24.04. These are the issues that came up and how they were solved.

## Disk and memory

- Move the WSL distribution off a full system drive before installing ROS:
  `wsl --manage Ubuntu-24.04 --move D:\WSL\Ubuntu-24.04`. ROS, Gazebo and PyTorch need about 15 GB.
- Give the VM enough memory. Gazebo, Nav2 and YOLO together use about 3–4 GB, plus swap
  for peaks. In `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=10GB
swap=8GB
swapFile=D:\\WSL\\swap.vhdx
networkingMode=mirrored
dnsTunneling=true
autoProxy=true
```

## Networking behind a VPN

With a corporate or university VPN (Cisco AnyConnect here), WSL's default NAT mode resolved
names but dropped all outgoing traffic. `networkingMode=mirrored` fixed it.

Mirrored mode has a side effect: connecting to a closed port on `127.0.0.1` hangs until a
timeout instead of being refused. The `ros2` command line probes its daemon that way, so
every `ros2 topic …` command crashed with `TimeoutError`. `scripts/setup_env.sh` checks the
daemon's port with `ss` (which never hangs) and starts the daemon first.

## Graphics

WSLg renders the Gazebo and RViz windows, but with an old AMD driver the GPU is not passed
through (`eglInitialize` fails for the `d3d12` Mesa driver) and everything renders on the
CPU with llvmpipe. Measured effects:

| Configuration | Real-time factor | Gazebo CPU |
|---|---|---|
| Upstream TurtleBot3 camera, 1920×1080 RGB at 30 Hz, GUI on | 0.14 | — |
| Same camera, GUI off | 0.42 | 680 % |
| findbot RGB-D camera, 640×480 at 10 Hz, GUI off | 0.42 | 190 % |

Lowering the camera resolution freed most of the CPU for Nav2 and YOLO, but did not raise
the real-time factor, so another sensor (most likely the GPU lidar, also rendered on the
CPU) is the remaining bottleneck. Run the simulation with `gui:=false` and watch it in RViz.
A current GPU driver should restore hardware rendering.
