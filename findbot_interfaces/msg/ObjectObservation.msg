# One object seen by the camera, localized in 3D.
# header.frame_id is the frame of `position` (normally "map"); header.stamp is the image time.
std_msgs/Header header

string label             # detector class name, e.g. "backpack"
string color             # dominant colour name, e.g. "red" ("" if unknown)
float32 confidence       # detector score, 0..1
geometry_msgs/Point position
float32 distance         # metres from the camera along its optical axis
