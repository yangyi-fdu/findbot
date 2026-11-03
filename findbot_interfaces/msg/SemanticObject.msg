# An object remembered in the semantic map (fused from many observations).
uint32 id
string label
string color                     # most frequently observed colour
geometry_msgs/Point position     # in the map frame
uint32 observations              # how many detections were fused into this object
float32 confidence               # mean detector score
builtin_interfaces/Time last_seen
