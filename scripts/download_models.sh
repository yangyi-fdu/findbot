#!/usr/bin/env bash
# Download the YOLO weights and the object models placed in findbot_world.
#   ~/findbot_models/yolo11n.pt
#   ~/findbot_models/gz/<name>/   (Gazebo Fuel models)
# Downloads run in parallel and resume, because a single connection can be very slow.
D=~/findbot_models
mkdir -p $D/gz
curl -sL -C - --retry 5 -o $D/yolo11n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt &

declare -A M=(
  [fire_hydrant]="OpenRobotics/models/Fire%20hydrant"
  [backpack_red]="OpenRobotics/models/JanSport%20Backpack%20Red"
  [chair]="OpenRobotics/models/Chair"
  [suitcase]="OpenRobotics/models/Suitcase1"
  [backpack_blue]="GoogleResearch/models/Jansport_School_Backpack_Blue_Streak"
  [standing_person]="OpenRobotics/models/Standing%20person"
)
fetch() {
  local name=$1 path=$2
  [ -f $D/gz/$name/model.config ] && { echo "have $name"; return; }
  for try in 1 2 3 4 5; do
    curl -sL -C - --retry 3 -o $D/gz/$name.zip "https://fuel.gazebosim.org/1.0/$path.zip" \
      && unzip -tq $D/gz/$name.zip >/dev/null 2>&1 && break
    sleep 3
  done
  rm -rf $D/gz/$name && mkdir $D/gz/$name && unzip -q $D/gz/$name.zip -d $D/gz/$name && rm $D/gz/$name.zip
  # The models refer to their own meshes as model://<original name>/...; we renamed the
  # folders, so make those references relative.
  find $D/gz/$name \( -name "*.sdf" -o -name "*.material" \) -exec sed -i -E 's#model://[^/<"]+/##g' {} +
  echo "downloaded $name"
}
for n in "${!M[@]}"; do fetch $n "${M[$n]}" & done
wait
for n in "${!M[@]}"; do printf "%-16s " $n; [ -f $D/gz/$n/model.config ] && echo ok || echo MISSING; done
printf "%-16s " yolo11n.pt; [ -s $D/yolo11n.pt ] && echo ok || echo MISSING
